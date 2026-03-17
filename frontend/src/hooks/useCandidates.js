import { useCallback, useEffect, useMemo, useState } from 'react';
import { supabase } from '../supabaseClient';

export function useCandidates(openMicId) {
  const [candidates, setCandidates] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [eventDate, setEventDate] = useState('');
  const [isValidated, setIsValidated] = useState(
    () => !!localStorage.getItem(`validated_${openMicId}`),
  );
  const [openMicConfig, setOpenMicConfig] = useState(null);

  const fetchCandidates = async () => {
    setLoading(true);
    setError('');

    let rows = [];
    let useLegacyView = false;
    let hasFechaEvento = true;

    const { data: dataV2, error: errorV2 } = await supabase
      .from('lineup_candidates')
      .select('solicitud_id,fecha_evento,nombre,genero,categoria,estado,score_final,comico_id,contacto,telefono,instagram,puede_hoy,is_single_date')
      .eq('open_mic_id', openMicId)
      .order('score_final', { ascending: false, nullsFirst: false });

    if (errorV2) {
      const isSchemaDrift = String(errorV2.message || '').includes('solicitud_id');
      if (!isSchemaDrift) {
        setError(errorV2.message);
        setLoading(false);
        return;
      }

      console.warn(
        'lineup_candidates sin columna solicitud_id en este entorno. Usando modo compatibilidad legacy.',
        { message: errorV2.message },
      );

      useLegacyView = true;
      const { data: dataLegacyWithDate, error: errorLegacyWithDate } = await supabase
        .from('lineup_candidates')
        .select('fecha_evento,nombre,genero,categoria,estado,score_final,comico_id,contacto,telefono,instagram')
        .order('score_final', { ascending: false, nullsFirst: false });

      if (errorLegacyWithDate) {
        const missingFechaEvento = String(errorLegacyWithDate.message || '').includes('fecha_evento');
        if (!missingFechaEvento) {
          setError(errorLegacyWithDate.message);
          setLoading(false);
          return;
        }

        hasFechaEvento = false;
        const { data: dataLegacy, error: errorLegacy } = await supabase
          .from('lineup_candidates')
          .select('nombre,genero,categoria,estado,score_final,comico_id,contacto,telefono,instagram')
          .order('score_final', { ascending: false, nullsFirst: false });

        if (errorLegacy) {
          setError(errorLegacy.message);
          setLoading(false);
          return;
        }

        rows = dataLegacy ?? [];
      } else {
        rows = dataLegacyWithDate ?? [];
      }
    } else {
      rows = dataV2 ?? [];
    }

    const normalized = rows.map((row, index) => ({
      ...row,
      solicitud_id: useLegacyView ? null : (row.solicitud_id ?? null),
      row_key: useLegacyView
        ? `${row.comico_id ?? 'unknown'}-${index}`
        : (row.solicitud_id ?? `${row.comico_id ?? 'unknown'}-${index}`),
      fecha_evento: hasFechaEvento ? (row.fecha_evento ?? null) : null,
      genero: row.genero === 'unknown' ? 'nb' : row.genero ?? 'nb',
      categoria: row.categoria ?? 'standard',
    }));
    const scoredFirst = normalized.filter((c) => c.estado === 'scorado');
    const pendingLegacy = normalized.filter((c) => c.estado === 'pendiente');
    const selectionSource =
      scoredFirst.length > 0 ? scoredFirst : (pendingLegacy.length > 0 ? pendingLegacy : normalized);
    const firstEventDate = selectionSource.find((c) => c.fecha_evento)?.fecha_evento;

    setCandidates(normalized);
    setSelectedIds(selectionSource.slice(0, 5).map((c) => c.row_key));
    if (firstEventDate) {
      setEventDate(firstEventDate);
    }

    // Detectar si ya está validado: hay slots confirmados en silver.lineup_slots
    const { data: slots } = await supabase
      .schema('silver')
      .from('lineup_slots')
      .select('id')
      .eq('open_mic_id', openMicId)
      .eq('status', 'confirmed')
      .limit(1);
    const confirmed = slots?.length > 0;
    setIsValidated(confirmed);
    if (confirmed) {
      localStorage.setItem(`validated_${openMicId}`, '1');
    } else {
      localStorage.removeItem(`validated_${openMicId}`);
    }

    setLoading(false);
  };

  useEffect(() => {
    fetchCandidates();
    supabase.schema('silver').from('open_mics').select('config').eq('id', openMicId).single()
      .then(({ data }) => { if (data?.config) setOpenMicConfig(data.config); });
  }, []);

  const toggleSelected = useCallback((candidateId) => {
    setSelectedIds((current) => {
      if (current.includes(candidateId)) {
        return current.filter((id) => id !== candidateId);
      }
      if (current.length >= 5) {
        return current;
      }
      return [...current, candidateId];
    });
  }, []);

  const selectedCandidates = useMemo(
    () => candidates.filter((c) => selectedIds.includes(c.row_key)),
    [candidates, selectedIds],
  );

  const isLastMinuteMode = useMemo(() => {
    if (!eventDate || !openMicConfig) return false;
    const scoringType = openMicConfig.scoring_type ?? 'basic';
    const hasBackupField =
      scoringType === 'basic' ||
      (scoringType === 'custom' &&
        Object.values(openMicConfig.field_mapping ?? {}).includes('backup'));
    if (!hasBackupField) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const event = new Date(eventDate + 'T00:00:00');
    const diffDays = Math.round((event - today) / (1000 * 60 * 60 * 24));
    return diffDays === 0 || diffDays === 1;
  }, [eventDate, openMicConfig]);

  const singleDateMode = useMemo(() => {
    if (!openMicConfig) return false;
    return openMicConfig.single_date_priority?.enabled !== false;
  }, [openMicConfig]);

  return {
    candidates, setCandidates, selectedIds, loading,
    error, setError, eventDate, setEventDate,
    isValidated, setIsValidated, openMicConfig,
    toggleSelected, selectedCandidates, isLastMinuteMode, singleDateMode,
  };
}

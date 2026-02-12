-- Agrega estados para gestión de reserva en la capa Silver.
ALTER TYPE public.tipo_solicitud_status ADD VALUE IF NOT EXISTS 'no_seleccionado';
ALTER TYPE public.tipo_solicitud_status ADD VALUE IF NOT EXISTS 'expirado';

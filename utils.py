# utils.py
from datetime import datetime, timedelta, time

def _hours_between(start: time, end: time) -> float:
    """
    Calcula horas entre dos objetos time (inicio, fin).
    Maneja turnos que pasan medianoche y días de descanso (None).
    """
    if start is None or end is None:
        return 0.0

    # Combina con una fecha ficticia (hoy) para poder restar datetimes
    dt_start = datetime.combine(datetime.today().date(), start)
    dt_end = datetime.combine(datetime.today().date(), end)

    # Si el fin es "antes" del inicio, asumimos que pasó medianoche
    if dt_end <= dt_start:
        dt_end += timedelta(days=1)

    delta = dt_end - dt_start
    return round(delta.total_seconds() / 3600.0, 2)

def calcular_horas_semana(horarios: dict) -> tuple[float, dict]:
    """
    horarios: dict como {"Lunes": (inicio, fin), ...}
    Devuelve (total_horas_semana, detalle_por_dia)
    """
    detalle = {}
    total = 0.0
    for dia, (ini, fin) in horarios.items():
        horas = _hours_between(ini, fin)
        detalle[dia] = horas
        total += horas
    # Redondeamos para estabilidad visual
    total = round(total, 2)
    return total, detalle

def calcular_nomina(row) -> float:
    """
    row es una Serie de pandas con columnas:
    - tipo ("Por horas" o "Fijo")
    - valor_hora, horas_semana, valor_cheque, valor_cash
    """
    tipo = row.get("tipo", "")
    if tipo == "Fijo":
        # Para fijos el total es cheque + cash
        return float(row.get("valor_cheque", 0.0)) + float(row.get("valor_cash", 0.0))
    else:
        # Por horas: valor_hora * horas_semana
        return float(row.get("valor_hora", 0.0)) * float(row.get("horas_semana", 0.0))

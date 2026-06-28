import functions_framework
import json
import math
from datetime import timedelta
from io import BytesIO
from fitparse import FitFile


def semicircles_to_degrees(semicircles):
    if semicircles is None:
        return None
    return semicircles * (180 / 2**31)


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def calculate_difficulty(tss):
    if tss is None:
        return None
    if tss < 100:
        return ""
    elif tss < 150:
        return ""
    elif tss < 250:
        return ""
    elif tss < 350:
        return ""
    else:
        return ""


def parse_fit_file(fit_data):
    # check_crc=False makes parsing tolerant of minor CRC mismatches in files
    # exported by some head units, and avoids an unnecessary full-file checksum pass.
    fitfile = FitFile(BytesIO(fit_data), check_crc=False)

    session = {}
    for record in fitfile.get_messages('session'):
        for field in record:
            session[field.name] = field.value

    # Walk the GPS track to find the point farthest from the start (turnaround).
    start_lat = None
    start_lon = None
    max_distance = 0
    farthest_lat = None
    farthest_lon = None

    for record in fitfile.get_messages('record'):
        record_data = {field.name: field.value for field in record}
        lat = semicircles_to_degrees(record_data.get('position_lat'))
        lon = semicircles_to_degrees(record_data.get('position_long'))
        if lat is None or lon is None:
            continue
        if start_lat is None:
            start_lat = lat
            start_lon = lon
            continue
        dist = haversine_distance(start_lat, start_lon, lat, lon)
        if dist > max_distance:
            max_distance = dist
            farthest_lat = lat
            farthest_lon = lon

    total_elapsed_time = session.get("total_elapsed_time")
    total_timer_time = session.get("total_timer_time")
    total_distance = session.get("total_distance")
    avg_speed = session.get("avg_speed")
    normalized_power = session.get("normalized_power")
    total_calories = session.get("total_calories")
    total_ascent = session.get("total_ascent")
    total_descent = session.get("total_descent")
    avg_cadence = session.get("avg_cadence")

    # Intensity factor: prefer the value recorded in the FIT session; otherwise
    # estimate it from normalized power against a default FTP.
    ftp = 200
    intensity_factor = session.get("intensity_factor")
    if intensity_factor is None and normalized_power:
        intensity_factor = normalized_power / ftp

    # Training Stress Score: prefer the value the head unit recorded (computed
    # with the rider's real FTP); fall back to the standard formula otherwise.
    tss = session.get("training_stress_score")
    if tss is None and normalized_power and total_elapsed_time and intensity_factor:
        tss = (total_elapsed_time * normalized_power * intensity_factor) / (ftp * 3600) * 100

    # FIT stores start_time in UTC; the automation wants it in KST (UTC+9).
    datetime_kst = None
    start_time = session.get("start_time")
    if start_time is not None:
        datetime_kst = (start_time + timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # IMPORTANT: this output shape is the contract the Make scenario reads
    # (`data.*` and `raw_session.*`). Renaming/moving these keys breaks the
    # downstream mapping (coordinates, Notion fields, dedup search).
    return {
        "data": {
            "datetime_kst": datetime_kst,
            "distance_km": round(total_distance / 1000, 2) if total_distance else None,
            "calories": total_calories,
            "total_ascent": total_ascent,
            "total_descent": total_descent,
            "tss": round(tss, 1) if tss else None,
            "avg_speed_kmh": round(avg_speed * 3.6, 1) if avg_speed else None,
            "avg_cadence": avg_cadence,
            "normalized_power": normalized_power,
            "intensity_factor": round(intensity_factor, 3) if intensity_factor else None,
            "difficulty": calculate_difficulty(tss),
            "farthest_point": {
                "latitude": farthest_lat,
                "longitude": farthest_lon,
                "distance_from_start_km": round(max_distance, 2),
            },
        },
        "raw_session": {
            "total_elapsed_time": total_elapsed_time,
            "total_timer_time": total_timer_time,
        },
    }


@functions_framework.http
def hello_http(request):
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
        return ('', 204, headers)

    headers = {'Access-Control-Allow-Origin': '*'}

    # Health check / manual probe: GET and HEAD return 200 instead of trying to
    # parse a (non-existent) body, so uptime checks don't look like failures.
    if request.method in ('GET', 'HEAD'):
        return (json.dumps({"status": "ok"}), 200,
                {**headers, 'Content-Type': 'application/json'})

    try:
        fit_data = request.get_data()
        if not fit_data:
            return (json.dumps({"error": "No data received"}), 400,
                    {**headers, 'Content-Type': 'application/json'})
        result = parse_fit_file(fit_data)
        return (json.dumps(result, default=str, ensure_ascii=False), 200,
                {**headers, 'Content-Type': 'application/json'})
    except Exception as e:
        # Log to stderr so the failure is visible in Cloud Run logs, then return
        # a 500 with the message (instead of letting the worker crash, which the
        # client sees as a 503 "Service Unavailable").
        import traceback
        traceback.print_exc()
        return (json.dumps({"error": str(e)}), 500,
                {**headers, 'Content-Type': 'application/json'})

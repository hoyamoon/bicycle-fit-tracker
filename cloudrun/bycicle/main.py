import functions_framework
import json
import math
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


def seconds_to_time_string(seconds):
    if seconds is None:
        return None
    seconds = round(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours} {minutes}"
    else:
        return f"{minutes}"


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
    result = {"session": {}, "farthest_point": {}, "calculated": {}}

    for record in fitfile.get_messages('session'):
        for field in record:
            result["session"][field.name] = field.value

    start_lat = None
    start_lon = None
    max_distance = 0
    farthest_lat = None
    farthest_lon = None

    for record in fitfile.get_messages('record'):
        record_data = {}
        for field in record:
            record_data[field.name] = field.value
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

    result["farthest_point"] = {
        "lat": farthest_lat,
        "lon": farthest_lon,
        "distance_from_start_km": round(max_distance, 2)
    }

    session = result["session"]
    total_elapsed_time = session.get("total_elapsed_time")
    total_distance = session.get("total_distance")
    avg_speed = session.get("avg_speed")
    max_speed = session.get("max_speed")
    avg_heart_rate = session.get("avg_heart_rate")
    max_heart_rate = session.get("max_heart_rate")
    avg_power = session.get("avg_power")
    normalized_power = session.get("normalized_power")
    total_calories = session.get("total_calories")
    total_ascent = session.get("total_ascent")
    total_descent = session.get("total_descent")
    avg_cadence = session.get("avg_cadence")

    tss = None
    if normalized_power and total_elapsed_time and avg_power:
        ftp = 200
        intensity_factor = normalized_power / ftp
        tss = (total_elapsed_time * normalized_power * intensity_factor) / (ftp * 3600) * 100

    result["calculated"] = {
        "elapsed_time_str": seconds_to_time_string(total_elapsed_time),
        "distance_km": round(total_distance / 1000, 2) if total_distance else None,
        "avg_speed_kmh": round(avg_speed * 3.6, 1) if avg_speed else None,
        "max_speed_kmh": round(max_speed * 3.6, 1) if max_speed else None,
        "avg_heart_rate": avg_heart_rate,
        "max_heart_rate": max_heart_rate,
        "avg_power": avg_power,
        "normalized_power": normalized_power,
        "total_calories": total_calories,
        "total_ascent": total_ascent,
        "total_descent": total_descent,
        "avg_cadence": avg_cadence,
        "tss": round(tss, 1) if tss else None,
        "difficulty": calculate_difficulty(tss)
    }
    return result


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

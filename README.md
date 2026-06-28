# bicycle-fit-tracker

  FIT     Notion DB   

## 

```
bicycle-fit-tracker/
 cloudrun/
    bycicle/
        main.py          # FIT   (Google Cloud Run)
        requirements.txt # Python 
        Dockerfile       # Cloud Run    
        deploy.sh        # Cloud Run /  
 make/
     make_bicycle_blueprint.json  # Make  blueprint
```

##  

### Google Cloud Run (`cloudrun/bycicle/`)
- **:** bycicle
- **:** asia-northeast3 ()
- **:** Python 3.10
- **URL:** https://bycicle-836077181090.asia-northeast3.run.app
- **:** Google Drive FIT      JSON 
- **:** fitparse==1.2.0

### Make  (`make/`)
- **:** make_bicycle
- **:**   10:50  
- **:** Google Drive  FIT (Cloud Run)     Notion DB 
- ** :** Notion Search  +      

## 배포 (Cloud Run)

`cloudrun/bycicle/` 디렉터리에서 실행:

```bash
cd cloudrun/bycicle
gcloud config set project <PROJECT_ID>   # 최초 1회
./deploy.sh
```

`deploy.sh`는 다음 플래그로 배포한다:

- `--allow-unauthenticated` — Make HTTP 모듈은 인증 없이 호출하므로 필수 (없으면 403 Forbidden)
- `--memory 512Mi` / `--timeout 300` — 실제 라이딩 FIT 파일 파싱 중 워커가 종료되지 않도록 여유 확보 (워커가 죽으면 클라이언트에는 503 Service Unavailable / ConnectionError 로 보임)

## 트러블슈팅

### Make 에서 `ConnectionError: Service Unavailable` (HTTP 모듈, Operation 3)

- **원인:** Make 시나리오 자체가 아니라 Cloud Run 엔드포인트 응답 문제다.
  - `503 Service Unavailable` — 컨테이너 리비전이 정상 기동/응답하지 못함 (기동 실패, 또는 요청 처리 중 워커 종료).
  - `403 Forbidden` — 서비스가 미인증 호출(`allUsers` invoker)을 허용하지 않음.
  - 2026.06.22 AWS Lambda → Cloud Run 이전 이후 FIT 파일이 있는 첫 실제 POST(06-27)부터 실패했다.
- **해결:** 위 `./deploy.sh` 로 재배포(권한·메모리·타임아웃 플래그 적용) 후 시나리오 재실행.
- Make HTTP 모듈에는 콜드스타트 대비로 `timeout: 300` 을 추가했다 (`make/make_bicycle_blueprint.json`). UI 에서도 HTTP 모듈 > Timeout = 300 으로 맞춰 두면 동일하다.

### Cloud Run 응답 형식 (Make 시나리오와의 계약)

`main.py` 가 돌려주는 JSON 구조는 Make 시나리오가 그대로 읽으므로 **키 이름/구조를 바꾸면 자동화가 깨진다.**

```json
{
  "data": {
    "datetime_kst": "YYYY-MM-DDTHH:MM:SS+09:00",
    "distance_km": 0,
    "calories": 0,
    "total_ascent": 0,
    "total_descent": 0,
    "tss": 0,
    "avg_speed_kmh": 0,
    "avg_cadence": 0,
    "normalized_power": 0,
    "intensity_factor": 0,
    "difficulty": "",
    "farthest_point": { "latitude": 0, "longitude": 0, "distance_from_start_km": 0 }
  },
  "raw_session": { "total_elapsed_time": 0, "total_timer_time": 0 }
}
```

- Make: `3.data` → `4`(Parse JSON) → `37`(Aggregator: `data`, `raw_session`) → `39`(SetVariables) → 카카오 지역코드 → Notion.
- `farthest_point.latitude/longitude` 가 비면 카카오 좌표→지역 변환이 `400 Bad Request` 로 실패한다.

##  
- 2026.06.22: AWS Lambda  Google Cloud Run  

"""
어제의 박스오피스 (KOBIS 일별 박스오피스 API)

이 파일 하나가 앱의 전부입니다.
Streamlit Cloud에 올릴 때는 이 파일과 requirements.txt를 같은 저장소에 두고,
앱 설정의 Secrets 칸에 아래 한 줄을 넣어 주세요.

    KOBIS_KEY = "발급받은_인증키"
"""

# ── 1. 필요한 도구들 불러오기 ───────────────────────────────────────────
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # 파이썬에 기본으로 들어 있는 시간대(timezone) 도구

import pandas as pd      # 표를 다루는 도구
import requests          # 인터넷 주소를 호출하는 도구
import streamlit as st   # 화면을 그리는 도구

# ── 2. 고정값 정리 ──────────────────────────────────────────────────────
# API 요청 주소 (공식 문서에 나온 그대로)
API_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

# 한국 시간대. 배포 서버 시계는 보통 UTC(세계 표준시)라서
# 서버 시계를 그대로 쓰면 날짜가 하루 어긋날 수 있습니다. 그래서 한국 시간으로 변환해 씁니다.
KST = ZoneInfo("Asia/Seoul")

# 화면 기본 설정 (제목, 아이콘, 넓은 레이아웃)
st.set_page_config(page_title="어제의 박스오피스", page_icon="🎬", layout="wide")


# ── 3. '어제' 날짜 계산하기 ────────────────────────────────────────────
def get_yesterday_kst() -> str:
    """한국 시간 기준 어제 날짜를 'yyyymmdd' 여덟 자리 문자열로 돌려줍니다.

    오늘 자료는 아직 집계 전이라 어제를 조회합니다.
    """
    now_kst = datetime.now(KST)          # 지금 시각을 한국 시간으로
    yesterday = now_kst - timedelta(days=1)  # 하루 빼기
    return yesterday.strftime("%Y%m%d")  # 예: 20260916


# ── 4. API 호출하기 (한 시간 동안 기억) ────────────────────────────────
# @st.cache_data(ttl=3600) 은 "같은 날짜로 다시 물으면 1시간(3600초) 동안은
# 인터넷을 다시 부르지 말고 저장해 둔 답을 그대로 쓰라"는 뜻입니다.
# 참고: 아래처럼 오류를 raise 하면 그 결과는 저장되지 않아서,
#       실패한 응답이 한 시간 동안 남아 있는 일은 생기지 않습니다.
@st.cache_data(ttl=3600, show_spinner="박스오피스를 불러오는 중입니다…")
def fetch_box_office(target_dt: str, api_key: str) -> dict:
    """KOBIS에 요청을 보내고 결과(JSON)를 사전(dict) 형태로 돌려줍니다."""
    params = {"key": api_key, "targetDt": target_dt}
    response = requests.get(API_URL, params=params, timeout=10)
    response.raise_for_status()  # 404, 500 같은 실패면 여기서 오류 발생
    return response.json()       # 응답이 JSON이 아니면 여기서 오류 발생


# ── 5. 응답을 표(DataFrame)로 바꾸기 ───────────────────────────────────
def to_dataframe(movie_list: list) -> pd.DataFrame:
    """영화 목록을 표로 만들고, 문자열로 온 숫자를 진짜 숫자로 바꿉니다."""
    df = pd.DataFrame(movie_list)

    # KOBIS는 숫자도 전부 글자("1", "123456")로 보내 줍니다.
    # 글자 상태로는 정렬이나 그래프가 엉뚱하게 나오므로 숫자로 변환합니다.
    # errors="coerce" 는 "숫자로 못 바꾸는 값은 빈 값으로 두라"는 뜻입니다.
    number_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
    for column in number_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    # 순위대로 정렬 (혹시 순서가 섞여서 와도 안전하게)
    df = df.sort_values("rank").reset_index(drop=True)

    # 사람이 읽기 좋은 한국어 이름으로 열 이름 바꾸기
    df = df.rename(
        columns={
            "rank": "순위",
            "movieNm": "영화명",
            "openDt": "개봉일",
            "audiCnt": "관객수",
            "audiAcc": "누적관객",
            "scrnCnt": "스크린수",
        }
    )
    return df


# ── 6. 오류 안내 문구 ──────────────────────────────────────────────────
def show_error(title: str, hints: list) -> None:
    """빈 화면 대신, 무엇을 확인해야 하는지 한국어로 알려 줍니다."""
    st.error(title)
    st.markdown("**확인해 볼 것**")
    for hint in hints:
        st.markdown(f"- {hint}")


# ── 7. 화면 그리기 (여기서부터 실제로 앱이 돌아갑니다) ─────────────────
st.title("🎬 어제의 박스오피스")

target_dt = get_yesterday_kst()
# 20260916 → 2026-09-16 처럼 보기 좋게 표시
pretty_date = f"{target_dt[:4]}-{target_dt[4:6]}-{target_dt[6:]}"
st.caption(f"조회 날짜: {pretty_date} (한국 시간 기준 어제) · 자료 출처: 영화진흥위원회(KOBIS)")

# 다시 불러오기 버튼: 저장해 둔 결과를 지우고 새로 호출합니다.
if st.button("🔄 새로 불러오기"):
    fetch_box_office.clear()
    st.rerun()

# (1) 인증키 확인 — 코드에 키를 적지 않고 비밀 금고(secrets)에서만 꺼냅니다.
api_key = st.secrets.get("KOBIS_KEY", "")
if not api_key:
    show_error(
        "인증키(KOBIS_KEY)를 찾지 못했습니다.",
        [
            "Streamlit Cloud 앱 화면에서 **Settings → Secrets** 를 엽니다.",
            '거기에 `KOBIS_KEY = "발급받은_인증키"` 를 한 줄 넣고 저장합니다.',
            "내 컴퓨터에서 실행 중이라면 `.streamlit/secrets.toml` 파일에 같은 줄을 넣습니다.",
            "저장한 뒤 앱을 다시 실행(Reboot)해야 반영됩니다.",
        ],
    )
    st.stop()  # 키가 없으면 여기서 멈춥니다.

# (2) API 호출 — 실패할 수 있으니 try 로 감쌉니다.
try:
    data = fetch_box_office(target_dt, api_key)
except requests.exceptions.Timeout:
    show_error(
        "요청 시간이 초과되었습니다.",
        ["잠시 뒤 **새로 불러오기** 버튼을 눌러 주세요.", "KOBIS 서버가 일시적으로 느릴 수 있습니다."],
    )
    st.stop()
except requests.exceptions.RequestException:
    show_error(
        "KOBIS 서버에 연결하지 못했습니다.",
        [
            "인터넷 연결 상태를 확인해 주세요.",
            "KOBIS 사이트(kobis.or.kr)가 점검 중인지 확인해 주세요.",
            "잠시 뒤 **새로 불러오기** 버튼을 눌러 주세요.",
        ],
    )
    st.stop()
except ValueError:
    show_error(
        "응답을 이해하지 못했습니다. (JSON 형식이 아님)",
        ["요청 주소가 `.json` 으로 끝나는지 확인해 주세요.", "KOBIS 서버 점검 중일 수 있습니다."],
    )
    st.stop()

# (3) faultInfo 상자 확인
# 인증키가 틀려도 상태코드는 200으로 정상처럼 오고, 대신 faultInfo 가 들어 있습니다.
if "faultInfo" in data:
    fault = data.get("faultInfo", {})
    message = fault.get("message", "알 수 없는 오류")
    code = fault.get("errorCode", "-")
    show_error(
        f"KOBIS가 오류를 돌려주었습니다. (코드 {code}: {message})",
        [
            "인증키가 정확한지, 앞뒤에 빈칸이나 따옴표가 섞이지 않았는지 확인해 주세요.",
            "발급받은 키가 만료되었거나 하루 호출 한도를 넘지 않았는지 확인해 주세요.",
            "KOBIS 오픈API 사이트에서 키 상태를 다시 확인해 주세요.",
        ],
    )
    st.stop()

# (4) 영화 목록 꺼내기 — 상자가 비어 있을 수 있으니 .get 으로 안전하게 꺼냅니다.
movie_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not movie_list:
    show_error(
        f"{pretty_date} 의 박스오피스 자료가 비어 있습니다.",
        [
            "해당 날짜의 집계가 아직 끝나지 않았을 수 있습니다. (보통 오전 중 갱신)",
            "잠시 뒤 **새로 불러오기** 버튼을 눌러 주세요.",
            "날짜가 너무 예전이면 자료가 없을 수 있습니다.",
        ],
    )
    st.stop()

# (5) 표로 변환
df = to_dataframe(movie_list)

# (6) 1위 영화 — 지표 카드 세 장
top_movie = df.iloc[0]  # 첫 번째 줄이 1위
st.subheader(f"🥇 1위 · {top_movie['영화명']}")

col1, col2, col3 = st.columns(3)
col1.metric("관객수", f"{int(top_movie['관객수']):,}명")
col2.metric("누적 관객", f"{int(top_movie['누적관객']):,}명")
col3.metric("스크린수", f"{int(top_movie['스크린수']):,}개")

st.divider()

# (7) 관객수 상위 5편 — 막대그래프
st.subheader("📊 관객수 상위 5편")
top5 = df.nlargest(5, "관객수")  # 관객수가 많은 순으로 5편
chart_data = top5.set_index("영화명")[["관객수"]]  # 가로축을 영화명으로
st.bar_chart(chart_data)

st.divider()

# (8) 전체 표
st.subheader("📋 전체 순위")
st.dataframe(
    df[["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]],
    hide_index=True,
    use_container_width=True,
    column_config={
        # 숫자에 천 단위 쉼표를 붙여 보여 줍니다. (정렬은 여전히 숫자 기준)
        "관객수": st.column_config.NumberColumn(format="%,d"),
        "누적관객": st.column_config.NumberColumn(format="%,d"),
        "스크린수": st.column_config.NumberColumn(format="%,d"),
    },
)

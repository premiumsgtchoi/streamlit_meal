# 1) 필요한 라이브러리 불러오기
import streamlit as st
import pandas as pd
from datetime import date
from datetime import timedelta
import requests
import re
import seaborn as sns
sns.set_theme(style="whitegrid")
sns.set_theme(style="whitegrid", rc={"font.family": "NanumGothic",
                                     "axes.unicode_minus": False})

import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

# 2) 페이지 기본 설정
st.set_page_config(page_title = "오늘 뭐먹지? - 건강 급식 가이드",
                   page_icon = "🍽️")

st.title("오늘 뭐먹지? - 건강 급식 가이드 🍽️")

# 3) 사용자 입력(위젯): 조회할 날짜 선택
#    - st.date_input은 달력 위젯을 보여주고, 결과를 datetime.date 객체로 반환
#    - value는 오늘 날짜로 설정
meal_date = st.date_input("조회하고 싶은 날짜를 선택하세요.",
                            value = date.today())

# --- [A] 알레르기 프로필(사이드바) & 매핑표 ---
ALLERGEN_MAP = {
    1:"난류",2:"우유",3:"메밀",4:"땅콩",5:"대두",6:"밀",7:"고등어",8:"게",
    9:"새우",10:"돼지고기",11:"복숭아",12:"토마토",13:"아황산류",
    14:"호두",15:"닭고기",16:"소고기",17:"오징어",18:"조개류(굴·전복·홍합 등)",19:"잣"
}

# 멀티셀렉트에 보여줄 옵션(라벨) 구성: "번호. 이름" 형태
ALLERGEN_OPTIONS = [f"{n}. {name}" for n, name in ALLERGEN_MAP.items()]

def _labels_from_numbers(nums: set[int]) -> list[str]:
    """기존 세션값이 숫자 집합일 때 멀티셀렉트 기본값 라벨로 변환"""
    return [f"{n}. {ALLERGEN_MAP[n]}" for n in sorted(nums) if n in ALLERGEN_MAP]

def _numbers_from_labels(labels: list[str]) -> set[int]:
    """멀티셀렉트에서 선택된 라벨들을 번호 집합으로 변환"""
    nums = set()
    for s in labels:
        # "15. 닭고기" -> 15
        try:
            nums.add(int(s.split(".")[0].strip()))
        except:
            pass
    return nums

with st.sidebar:
    st.subheader("알레르기 프로필")

    # 이전 세션에서 선택한 번호 집합 복원(없으면 빈 집합)
    prev_nums = st.session_state.get("MY_ALLERGENS", set())

    selected_labels = st.multiselect(
        """조회할 알레르기 성분을 모두 선택하세요.""",
        options=ALLERGEN_OPTIONS,
        default=_labels_from_numbers(prev_nums)
    )

    # 최종 번호 집합
    MY_ALLERGENS = _numbers_from_labels(selected_labels)
    st.session_state["MY_ALLERGENS"] = MY_ALLERGENS  # 세션 유지

    # 편의: 선택 요약
    if MY_ALLERGENS:
        st.caption(
            "선택: " + ", ".join(f"{n}({ALLERGEN_MAP[n]})" for n in sorted(MY_ALLERGENS))
        )
    else:
        st.caption("선택된 알레르기 성분 없음")

    only_risky = st.checkbox("⚠️ 주의 메뉴만 보기", value=False)

    st.markdown("---")
    st.markdown("**ℹ️ 알레르기 번호 안내**")
    st.caption(
        "1: 난류 · 2: 우유 · 3: 메밀 · 4: 땅콩 · 5: 대두 · 6: 밀 · 7: 고등어 · 8: 게 · 9: 새우 · "
        "10: 돼지고기 · 11: 복숭아 · 12: 토마토 · 13: 아황산류 · 14: 호두 · 15: 닭고기 · "
        "16: 소고기 · 17: 오징어 · 18: 조개류(굴·전복·홍합 등) · 19: 잣"
    )

# 4-1) 함수: 특정 날짜(문자열)로 NEIS 급식 API 호출 → 표(데이터프레임)로 반환
#    - date_str 예: "20250811" (YYYYMMDD 형식)
#    - st.secrets는 .streamlit/secrets.toml 파일에 저장한 값(API)을 읽어옴
@st.cache_data(ttl=3600, show_spinner=False)
def get_meal_info(date_str):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": st.secrets["neis"]["KEY"],
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": st.secrets["neis"]["ATPT"],
        "SD_SCHUL_CODE": st.secrets["neis"]["SCHUL"],
        "MLSV_YMD": date_str
    }
    res = requests.get(url, params=params)
    data = res.json()

    if "mealServiceDietInfo" in data:
        rows = data["mealServiceDietInfo"][1]["row"]
        return pd.DataFrame(rows)
    else:
        return pd.DataFrame()
    
# 메뉴 문자열을 리스트로 분리 (<br/> 기준, 없으면 / , 로도 분리 보조)
def split_menu_items(menu_text: str):
    if not isinstance(menu_text, str):
        return []
    if "<br/>" in menu_text:
        parts = menu_text.split("<br/>")
    else:
        parts = re.split(r"[\/,]", menu_text)
    return [p.strip() for p in parts if p.strip()]

# 메뉴 항목에 포함된 알레르기 번호 집합 추출: 예) "어묵국(5,6,13)" -> {5,6,13}
def extract_allergen_numbers(item: str):
    if not isinstance(item, str):
        return set()
    m = re.search(r"\(([\d,\s]+)\)", item)
    if not m:
        return set()
    nums = [n.strip() for n in m.group(1).split(",") if n.strip().isdigit()]
    return set(map(int, nums))

# 칼로리 문자열에서 숫자만 추출: "824.00 Kcal" -> 824.0
def parse_kcal(cal_info: str):
    if not isinstance(cal_info, str):
        return None
    m = re.search(r"([\d.]+)", cal_info)
    return float(m.group(1)) if m else None

# 영양정보 문자열 파싱 (포맷이 다양해서 '키:값' 패턴 위주로 안전 파싱)
# 예: "탄수화물(g): 120 / 단백질(g): 35 / 지방(g): 20" -> dict
def parse_nutrients(ntr_info: str):
    if not isinstance(ntr_info, str):
        return {}
    # 구분자는 / 또는 , 기준으로 쪼갠 뒤, 키:값 패턴만 수집
    parts = re.split(r"[\/,]", ntr_info)
    result = {}
    for p in parts:
        if ":" in p:
            k, v = p.split(":", 1)
            k = k.strip()
            v = v.strip()
            # 값에서 숫자만 우선 추출(단위는 표시용으로 남겨둠)
            m = re.search(r"([\d.]+)", v)
            result[k] = float(m.group(1)) if m else v
    return result

# 5) 날짜 객체를 API가 요구하는 문자열(YYYYMMDD)로 변환
date_str = meal_date.strftime("%Y%m%d")
df = get_meal_info(date_str)

# 6) 화면 표시
if df.empty:
    st.warning("해당 날짜의 급식 정보가 없습니다.")
else:
    # 중식만 사용: 혹시 여러 끼니가 함께 올 경우를 대비해 중식 행만 우선 선택
    # (데이터에 따라 MMEAL_SC_NM이 없을 수도 있어 예외 처리)
    if "MMEAL_SC_NM" in df.columns:
        lunch_df = df[df["MMEAL_SC_NM"].str.contains("중식", na=False)]
        base = lunch_df.iloc[0] if len(lunch_df) else df.iloc[0]
    else:
        base = df.iloc[0]

    # 필드 안전 추출
    menu_raw = str(base.get("DDISH_NM", ""))
    cal_raw  = str(base.get("CAL_INFO", ""))
    ntr_raw  = str(base.get("NTR_INFO", ""))
    # 보기 좋게 파싱
    menu_items = split_menu_items(menu_raw)
    kcal = parse_kcal(cal_raw)
    nutrients = parse_nutrients(ntr_raw)

    st.subheader(f"{meal_date} 급식 정보 (중식)")

    # ── 탭 생성
    tab1, tab2, tab3 = st.tabs(["🍽 메뉴", "⚠ 알레르기", "🧪 영양 & 칼로리"])

    # 🍽 메뉴 탭 (간결 버전: 경고 아이콘만 표시)
    with tab1:
        st.subheader("🍽 오늘의 메뉴")

        if not menu_items:
            st.info("메뉴 정보가 없습니다.")
        else:
            lines = []
            for it in menu_items:
                overlap = extract_allergen_numbers(it) & MY_ALLERGENS
                is_risky = bool(overlap)

                # 사이드바에서 '주의 메뉴만 보기' 켜진 경우, 안전 항목은 숨김
                if only_risky and not is_risky:
                    continue

                icon = " ⚠️" if is_risky else ""   # 경고 아이콘만
                lines.append(f"- {it}{icon}")

            if lines:
                # 불릿 리스트로 깔끔하게 출력
                st.markdown("\n".join(lines))
                st.caption("⚠️ 표시는 ‘알레르기 프로필’과 겹치는 메뉴입니다. 상세 정보는 [⚠ 알레르기] 탭에서 확인하세요.")
            else:
                st.info("표시할 메뉴가 없습니다.")

    # ⚠ 알레르기 탭 (위험 메뉴 중심으로 개편)
    with tab2:
        st.subheader("⚠ 알레르기 위험 메뉴")

        if not menu_items:
            st.info("알레르기 정보를 표시할 메뉴가 없습니다.")
        else:
            rows = []
            risky_count = 0

            for it in menu_items:
                nums = extract_allergen_numbers(it)       # 해당 메뉴에 표기된 알레르기 번호 집합
                if MY_ALLERGENS:                          # 내 프로필이 설정된 경우
                    overlap = sorted(nums & MY_ALLERGENS) # 내 프로필과 겹치는 번호만
                    if not overlap:
                        continue                          # 위험이 없으면 표에서 제외
                    risky_count += 1
                    labels = [f"{n}({ALLERGEN_MAP.get(n, '?')})" for n in overlap]
                    rows.append({
                        "메뉴": it,
                        "해당 알레르기(내 프로필)": ", ".join(labels)
                    })
                else:
                    # 내 프로필이 비어 있으면, 메뉴별로 '탐지된 모든 알레르기'를 안내용으로 노출
                    if nums:
                        labels = [f"{n}({ALLERGEN_MAP.get(n, '?')})" for n in sorted(nums)]
                        rows.append({
                            "메뉴": it,
                            "탐지된 알레르기(안내)": ", ".join(labels)
                        })

            if MY_ALLERGENS:
                if rows:
                    st.warning(f"내 알레르기 프로필 기준, 위험 메뉴 {risky_count}개가 있습니다.")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.success("오늘 메뉴에는 내 알레르기 성분이 포함되지 않았습니다.")
                st.caption(
                    "표시 기준: 사이드바에서 선택한 알레르기 번호와 겹치는 메뉴만 보여줍니다."
                )
            else:
                if rows:
                    st.info("내 프로필이 설정되지 않았습니다. 아래는 안내용으로 탐지된 알레르기입니다.")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    st.caption("사이드바에서 알레르기 성분을 선택하면 ‘내 프로필 기준’ 위험 메뉴만 필터링됩니다.")
                else:
                    st.info("표시할 알레르기 표기 메뉴가 없습니다.")


    # 🧪 영양 & 칼로리 탭
    with tab3:
        st.subheader("🧪 영양 & 칼로리")
        if kcal is not None:
            st.metric("**총 열량 (Kcal)**", f"{kcal:.0f}Kcal")
        else:
            st.metric("총 열량 (Kcal)", "정보 없음")

        # ---------- 주요 영양성분 막대 그래프 (seaborn 버전) ----------
        st.markdown("**주요 영양성분(g) 비교**")

        def to_grams(key: str, val: float):
            """키 문자열의 단위 표기를 보고 mg는 g로 변환"""
            k = str(key)
            if "(mg)" in k or "mg" in k:
                return val / 1000.0
            return val

        macro_map = {"탄수": None, "단백": None, "지방": None}
        for k, v in nutrients.items():
            if not isinstance(v, (int, float)):
                continue
            for token in macro_map.keys():
                if token in k:
                    macro_map[token] = to_grams(k, float(v))

        label_map = {"탄수": "탄수화물(g)", "단백": "단백질(g)", "지방": "지방(g)"}
        data = []
        for token in ["탄수", "단백", "지방"]:
            val = macro_map.get(token)
            if isinstance(val, (int, float)) and val > 0:
                data.append({"성분": label_map[token], "값(g)": val})

        if data:
            df_macro = pd.DataFrame(data)

            fig, ax = plt.subplots(figsize=(6, 4))
            sns.barplot(data=df_macro, x="성분", y="값(g)", palette="pastel", ax=ax)

            # 수치 라벨 추가
            for p in ax.patches:
                ax.annotate(f"{p.get_height():.1f}",
                            (p.get_x() + p.get_width() / 2., p.get_height()),
                            ha='center', va='bottom', fontsize=11)

            ax.set_ylabel("g", fontsize=11)
            ax.set_title("주요 영양성분", fontsize=13, pad=8)
            ax.yaxis.grid(True, linestyle="--", alpha=0.35)
            ax.set_axisbelow(True)

            st.pyplot(fig)
        else:
            st.info("탄수화물/단백질/지방 정보가 부족해 그래프를 표시할 수 없습니다.")

        if nutrients:
            st.markdown("**영양성분표**")
            ntr_df = pd.DataFrame(
                [{"성분": k, "값": v} for k, v in nutrients.items()]
            ).sort_values("성분").reset_index(drop=True)
            st.dataframe(ntr_df, use_container_width=True, hide_index=True)
        else:
            st.info("영양정보가 없습니다.")

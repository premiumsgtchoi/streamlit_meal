# ─────────────────────────────────────────────────────────────────────────────
# 1) 환경/라이브러리 & 폰트 세팅
#     1-1) 기본 라이브러리 임포트
#     1-2) 한글 폰트 파일 준비(없으면 다운로드)
#     1-3) 폰트 등록 및 Seaborn 테마 적용
# ─────────────────────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
from datetime import date
import requests
import re

# 1-2) 한글 폰트 파일 준비(없으면 다운로드)
import urllib.request
from pathlib import Path
FONT_FILE = Path("assets/NanumGothic.ttf")
if not FONT_FILE.exists():
    FONT_FILE.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(
        "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf",
        FONT_FILE.as_posix()
    )

# 1-3) 폰트 등록 + 시각화 테마 적용
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
fm.fontManager.addfont(FONT_FILE.as_posix())          # 폰트 등록
plt.rcParams["font.family"] = "NanumGothic"           # Matplotlib 기본 폰트
plt.rcParams["axes.unicode_minus"] = False            # 음수 기호 깨짐 방지
sns.set_theme(style="whitegrid",
              rc={"font.family": "NanumGothic", "axes.unicode_minus": False})

# ─────────────────────────────────────────────────────────────────────────────
# 2) 앱 기본 설정
#     2-1) 페이지 타이틀/아이콘
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="오늘 뭐먹지? - 건강 급식 가이드", page_icon="🍽️")
st.title("오늘 뭐먹지? - 건강 급식 가이드 🍽️")

# ─────────────────────────────────────────────────────────────────────────────
# 3) 사용자 입력 위젯 & 사이드바
#     3-1) 날짜 선택 위젯
#     3-2) 알레르기 번호 사전(번호→이름)
#     3-3) 멀티셀렉트 라벨/번호 변환 함수
#     3-4) 사이드바: 알레르기 프로필(멀티셀렉트) + 필터 토글
#     3-5) 사이드바: 일일 권장 섭취량(프리셋/직접 입력)
# ─────────────────────────────────────────────────────────────────────────────
# 3-1) 날짜 선택
meal_date = st.date_input("조회하고 싶은 날짜를 선택하세요.", value=date.today())

# 3-2) 알레르기 번호 매핑
ALLERGEN_MAP = {
    1: "난류", 2: "우유", 3: "메밀", 4: "땅콩", 5: "대두", 6: "밀", 7: "고등어", 8: "게",
    9: "새우", 10: "돼지고기", 11: "복숭아", 12: "토마토", 13: "아황산류",
    14: "호두", 15: "닭고기", 16: "소고기", 17: "오징어", 18: "조개류(굴·전복·홍합 등)", 19: "잣"
}
ALLERGEN_OPTIONS = [f"{n}. {name}" for n, name in ALLERGEN_MAP.items()]  # UI용 라벨

# 3-3) 라벨↔번호 변환
def _labels_from_numbers(nums: set[int]) -> list[str]:
    """선택했던 번호 집합 → 멀티셀렉트 기본값 라벨 리스트"""
    return [f"{n}. {ALLERGEN_MAP[n]}" for n in sorted(nums) if n in ALLERGEN_MAP]

def _numbers_from_labels(labels: list[str]) -> set[int]:
    """멀티셀렉트 라벨 리스트 → 번호 집합"""
    nums = set()
    for s in labels:
        try:
            nums.add(int(s.split(".")[0].strip()))
        except:
            pass
    return nums

# 3-4) 사이드바: 알레르기 프로필 + 필터
with st.sidebar:
    st.subheader("알레르기 프로필")
    prev_nums = st.session_state.get("MY_ALLERGENS", set())
    selected_labels = st.multiselect(
        "조회할 알레르기 성분을 모두 선택하세요.",
        options=ALLERGEN_OPTIONS,
        default=_labels_from_numbers(prev_nums),
    )
    MY_ALLERGENS = _numbers_from_labels(selected_labels)
    st.session_state["MY_ALLERGENS"] = MY_ALLERGENS

    # 선택 요약
    if MY_ALLERGENS:
        st.caption("선택: " + ", ".join(f"{n}({ALLERGEN_MAP[n]})" for n in sorted(MY_ALLERGENS)))
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

    # 3-5) 일일 권장 섭취량 설정(프리셋 + 커스텀)
    st.markdown("---")
    st.subheader("권장 섭취량(일일)")
    PRESETS = {
        "기본(수정 가능)": {"kcal": 2200, "carb_g": 330, "prot_g": 55, "fat_g": 65},
        "초등 고학년(10~12세)": {"kcal": 2000, "carb_g": 300, "prot_g": 45, "fat_g": 60},
        "중등(13~15세)": {"kcal": 2300, "carb_g": 340, "prot_g": 55, "fat_g": 70},
        "고등(16~18세)": {"kcal": 2600, "carb_g": 360, "prot_g": 65, "fat_g": 80},
    }
    preset = st.selectbox("기준 선택", list(PRESETS.keys()), index=1)
    p = PRESETS[preset]
    kcal_target = st.number_input("열량(kcal/일)", min_value=500, max_value=4000, value=p["kcal"], step=50)
    carb_target = st.number_input("탄수화물(g/일)", min_value=50, max_value=800, value=p["carb_g"], step=10)
    prot_target = st.number_input("단백질(g/일)", min_value=10, max_value=200, value=p["prot_g"], step=5)
    fat_target  = st.number_input("지방(g/일)",   min_value=10, max_value=200, value=p["fat_g"],  step=5)
    st.session_state["targets"] = {"kcal": kcal_target, "carb_g": carb_target, "prot_g": prot_target, "fat_g": fat_target}

# ─────────────────────────────────────────────────────────────────────────────
# 4) 데이터 처리 함수
#     4-1) NEIS API 호출 → DataFrame
#     4-2) 메뉴 문자열 분해
#     4-3) 메뉴의 알레르기 번호 추출
#     4-4) 칼로리 숫자만 추출
#     4-5) 영양정보 문자열 파싱(dict)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_meal_info(date_str: str) -> pd.DataFrame:
    """4-1) 날짜(YYYYMMDD) 기준 급식 데이터 조회"""
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": st.secrets["neis"]["KEY"], "Type": "json",
        "pIndex": 1, "pSize": 100,
        "ATPT_OFCDC_SC_CODE": st.secrets["neis"]["ATPT"],
        "SD_SCHUL_CODE": st.secrets["neis"]["SCHUL"],
        "MLSV_YMD": date_str
    }
    res = requests.get(url, params=params)
    data = res.json()
    if "mealServiceDietInfo" in data:
        rows = data["mealServiceDietInfo"][1]["row"]
        return pd.DataFrame(rows)
    return pd.DataFrame()

def split_menu_items(menu_text: str) -> list[str]:
    """4-2) 메뉴 문자열을 항목 리스트로 분해(<br/> 우선, 없으면 / , 기준)"""
    if not isinstance(menu_text, str):
        return []
    parts = menu_text.split("<br/>") if "<br/>" in menu_text else re.split(r"[\/,]", menu_text)
    return [p.strip() for p in parts if p.strip()]

def extract_allergen_numbers(item: str) -> set[int]:
    """4-3) '어묵국(5,6,13)' → {5,6,13} 형태의 번호 집합"""
    if not isinstance(item, str):
        return set()
    m = re.search(r"\(([\d,\s]+)\)", item)
    if not m:
        return set()
    nums = [n.strip() for n in m.group(1).split(",") if n.strip().isdigit()]
    return set(map(int, nums))

def parse_kcal(cal_info: str):
    """4-4) '824.00 Kcal' → 824.0 (숫자만 추출)"""
    if not isinstance(cal_info, str):
        return None
    m = re.search(r"([\d.]+)", cal_info)
    return float(m.group(1)) if m else None

def parse_nutrients(ntr_info: str) -> dict:
    """4-5) '탄수화물(g):120 / 단백질(g):35 ...' → {'탄수화물(g)':120, ...}"""
    if not isinstance(ntr_info, str):
        return {}
    parts = re.split(r"[\/,]", ntr_info)
    result = {}
    for p in parts:
        if ":" in p:
            k, v = p.split(":", 1)
            k, v = k.strip(), v.strip()
            m = re.search(r"([\d.]+)", v)
            result[k] = float(m.group(1)) if m else v
    return result

# ─────────────────────────────────────────────────────────────────────────────
# 5) 데이터 가져오기
#     5-1) 날짜 문자열 만들기 → API 호출
# ─────────────────────────────────────────────────────────────────────────────
date_str = meal_date.strftime("%Y%m%d")
df = get_meal_info(date_str)

# ─────────────────────────────────────────────────────────────────────────────
# 6) 화면 구성
#     6-1) 데이터 유무에 따라 안내
#     6-2) 탭1: 오늘의 메뉴(경고 아이콘만)
#     6-3) 탭2: 알레르기 위험 메뉴(내 프로필 기준)
#     6-4) 탭3: 영양 & 칼로리(막대그래프 + 권장치 대비 퍼센트 + 성분표)
# ─────────────────────────────────────────────────────────────────────────────
if df.empty:
    st.warning("해당 날짜의 급식 정보가 없습니다.")
else:
    # 6-1) 중식 우선 선택(없으면 첫 행 사용)
    if "MMEAL_SC_NM" in df.columns:
        lunch_df = df[df["MMEAL_SC_NM"].str.contains("중식", na=False)]
        base = lunch_df.iloc[0] if len(lunch_df) else df.iloc[0]
    else:
        base = df.iloc[0]

    # 공통 데이터 파싱
    menu_raw = str(base.get("DDISH_NM", ""))
    cal_raw  = str(base.get("CAL_INFO", ""))
    ntr_raw  = str(base.get("NTR_INFO", ""))
    menu_items = split_menu_items(menu_raw)
    kcal = parse_kcal(cal_raw)
    nutrients = parse_nutrients(ntr_raw)

    st.subheader(f"{meal_date} 급식 정보 (중식)")

    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["🍽 메뉴", "⚠ 알레르기", "🧪 영양 & 칼로리"])

    # 6-2) 탭1: 오늘의 메뉴(경고 아이콘만 표시)
    with tab1:
        st.subheader("🍽 오늘의 메뉴")
        if not menu_items:
            st.info("메뉴 정보가 없습니다.")
        else:
            lines = []
            for it in menu_items:
                overlap = extract_allergen_numbers(it) & MY_ALLERGENS
                is_risky = bool(overlap)
                if only_risky and not is_risky:   # '주의 메뉴만' 필터
                    continue
                icon = " ⚠️" if is_risky else ""
                lines.append(f"- {it}{icon}")
            if lines:
                st.markdown("\n".join(lines))
                st.caption("⚠️ 표시는 ‘알레르기 프로필’과 겹치는 메뉴입니다. 상세 내용은 [⚠ 알레르기] 탭 참고.")
            else:
                st.info("표시할 메뉴가 없습니다.")

    # 6-3) 탭2: 알레르기 위험 메뉴(내 프로필 기준)
    with tab2:
        st.subheader("⚠ 알레르기 위험 메뉴")
        if not menu_items:
            st.info("알레르기 정보를 표시할 메뉴가 없습니다.")
        else:
            rows, risky_count = [], 0
            for it in menu_items:
                nums = extract_allergen_numbers(it)
                if MY_ALLERGENS:
                    overlap = sorted(nums & MY_ALLERGENS)
                    if not overlap:
                        continue
                    risky_count += 1
                    labels = [f"{n}({ALLERGEN_MAP.get(n, '?')})" for n in overlap]
                    rows.append({"메뉴": it, "해당 알레르기(내 프로필)": ", ".join(labels)})
                else:
                    if nums:
                        labels = [f"{n}({ALLERGEN_MAP.get(n, '?')})" for n in sorted(nums)]
                        rows.append({"메뉴": it, "알레르기(안내)": ", ".join(labels)})

            if MY_ALLERGENS:
                if rows:
                    st.warning(f"내 알레르기 프로필 기준, 위험 메뉴 {risky_count}개가 있습니다.")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.success("오늘 메뉴에는 내 알레르기 성분이 포함되지 않았습니다.")
                st.caption("표시 기준: 사이드바에서 선택한 번호와 겹치는 메뉴만 보여줍니다.")
            else:
                if rows:
                    st.info("내 프로필이 설정되지 않았습니다. 아래는 안내용으로 탐지된 알레르기입니다.")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    st.caption("사이드바에서 성분을 선택하면 ‘내 프로필 기준’으로 필터링됩니다.")
                else:
                    st.info("표시할 알레르기 표기 메뉴가 없습니다.")

    # 6-4) 탭3: 영양 & 칼로리(그래프/퍼센트/표)
    with tab3:
        st.subheader("🧪 영양 & 칼로리")

        # (a) 총열량 카드
        if kcal is not None:
            st.metric("**총 열량 (Kcal)**", f"{kcal:.0f}Kcal")
        else:
            st.metric("총 열량 (Kcal)", "정보 없음")

        # (b) 주요 영양성분(g) 막대그래프: 탄수/단백/지방
        st.markdown("**주요 영양성분(g) 비교**")

        def to_grams(key: str, val: float):
            """단위가 mg면 g로 변환"""
            if "(mg)" in key or "mg" in key:
                return float(val) / 1000.0
            return float(val)

        macro_map = {"탄수": None, "단백": None, "지방": None}
        for k, v in nutrients.items():
            if not isinstance(v, (int, float)):
                continue
            for token in macro_map.keys():
                if token in k:
                    macro_map[token] = to_grams(k, v)

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
            for p in ax.patches:  # 막대 위 수치 라벨
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

        # (c) 일일 권장 섭취량 대비 퍼센트(Progress Bar)
        st.markdown("**권장 섭취량 비율 (일일 기준 %)**")
        targets = st.session_state.get("targets", {"kcal": 2200, "carb_g": 330, "prot_g": 55, "fat_g": 65})

        def get_macro_val(name: str):
            try:
                return float(next(d["값(g)"] for d in data if d["성분"].startswith(name)))
            except StopIteration:
                return None

        carb_val = get_macro_val("탄수화물")
        prot_val = get_macro_val("단백질")
        fat_val  = get_macro_val("지방")
        kcal_val = kcal

        def pct(val, target):
            if not val or not target or target <= 0:
                return None
            return round(val / target * 100)

        pct_carb = pct(carb_val, targets["carb_g"])
        pct_prot = pct(prot_val, targets["prot_g"])
        pct_fat  = pct(fat_val,  targets["fat_g"])
        pct_kcal = pct(kcal_val, targets["kcal"])

        cols = st.columns(4)
        labels = [("열량", pct_kcal), ("탄수화물", pct_carb), ("단백질", pct_prot), ("지방", pct_fat)]
        for col, (lab, p) in zip(cols, labels):
            with col:
                st.write(f"**{lab}**")
                if p is None:
                    st.write("정보 없음")
                    st.progress(0)
                else:
                    # 색상: 과다(≥100%) 주황, 권장(80~99%) 초록, 부족(<80%) 파랑
                    color = "orange" if p >= 50 else ("green" if p >= 33 else "blue")
                    st.markdown(
                        f"<span style='font-size:20px; font-weight:bold; color:{color}'>{p}%</span>",
                        unsafe_allow_html=True
                    )
                    st.progress(min(100, max(0, p)))
        st.caption("※ 한 끼 섭취량을 ‘일일 권장 섭취량’과 비교한 값입니다. 기준치는 사이드바에서 조정하세요.")

        # (d) 영양성분 원본 표(참고용)
        if nutrients:
            st.markdown("**영양성분표**")
            ntr_df = pd.DataFrame([{"성분": k, "값": v} for k, v in nutrients.items()]) \
                        .sort_values("성분").reset_index(drop=True)
            st.dataframe(ntr_df, use_container_width=True, hide_index=True)
        else:
            st.info("영양정보가 없습니다.")

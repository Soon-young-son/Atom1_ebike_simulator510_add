import streamlit as st
import pandas as pd
import math

# --- 페이지 기본 설정 (다크 테마 느낌) ---
st.set_page_config(page_title="Atom1 E-bike 시뮬레이터", layout="wide")

# --- 물리 엔진 클래스 ---
class Atom1Controller:
    RPM_STEPS = [0, 640, 960, 1280, 1600, 1750]
    MODES = ['F', 'E', 'D', 'C', 'B', 'A']
    
    WHEEL_TORQUE_MAP = {
        640:  {'A':4, 'B':4, 'C':4, 'D':4, 'E':4, 'F':4},
        960:  {'A':6, 'B':5, 'C':4, 'D':4, 'E':4, 'F':4},
        1280: {'A':8, 'B':6, 'C':5, 'D':3, 'E':3, 'F':2},
        1600: {'A':10, 'B':7, 'C':5, 'D':4, 'E':3, 'F':2},
        1750: {'A':10, 'B':7, 'C':6, 'D':4, 'E':3, 'F':1}
    }
    
    # 모드별 전류량 (화면 표시용)
    CURRENT_MAP = {
        640:  {'A':6.94, 'B':6.94, 'C':6.94, 'D':6.94, 'E':6.94, 'F':6.94},
        960:  {'A':6.94, 'B':6.94, 'C':6.00, 'D':5.00, 'E':4.00, 'F':3.00},
        1280: {'A':6.94, 'B':6.00, 'C':5.00, 'D':4.00, 'E':3.00, 'F':2.00},
        1600: {'A':6.94, 'B':5.00, 'C':4.00, 'D':3.00, 'E':2.00, 'F':1.50},
        1750: {'A':6.94, 'B':5.00, 'C':4.00, 'D':3.00, 'E':2.00, 'F':1.00}
    }

    def simulate_state(self, target_rpm, mode_idx, slope_percent, rider_torque):
        if target_rpm == 0:
            return {"모드": "-", "전류": 0, "실제RPM": 0, "속도": 0, "요구토크": 0, "가용토크": 0, "매핑RPM": 0}

        map_rpm = min(self.RPM_STEPS[1:], key=lambda k: abs(k - target_rpm))
        active_mode = self.MODES[mode_idx]
        
        motor_torque = self.WHEEL_TORQUE_MAP[map_rpm][active_mode]
        avail_torque = motor_torque + rider_torque
        
        angle_rad = math.atan(slope_percent / 100.0)
        req_torque = (90.0 * 9.81 * math.sin(angle_rad) * 0.254) + 2.0

        # 토크 차이에 따른 RPM 연산
        if avail_torque < req_torque:
            actual_rpm = target_rpm * (avail_torque / req_torque)
        else:
            surge = min(0.15, (avail_torque - req_torque) / max(1.0, avail_torque))
            actual_rpm = target_rpm * (1.0 + surge)

        ring_rpm = actual_rpm / 32.0
        chainring_rpm = (3 * 50) + (2 * ring_rpm)
        speed_kmh = (chainring_rpm * (20.0 / 28.0)) * 0.09576 

        return {
            "모드": active_mode, 
            "전류": self.CURRENT_MAP[map_rpm][active_mode],
            "실제RPM": int(actual_rpm),
            "속도": round(speed_kmh, 1),
            "요구토크": req_torque, 
            "가용토크": avail_torque,
            "매핑RPM": map_rpm  # 매핑 테이블용 키 추가
        }

# --- 세션 상태 초기화 ---
if 'target_rpm' not in st.session_state: st.session_state.target_rpm = 1600
if 'mode_idx' not in st.session_state: st.session_state.mode_idx = 1 # E 모드

# --- UI 레이아웃 ---
st.title("🚲 Atom1 E-bike 시뮬레이터")

# 사이드바 입력
st.sidebar.header("🎛️ 제어 패널")
col1, col2 = st.sidebar.columns(2)
if col1.button("🔼 단계 올림 (Up)"):
    idx = Atom1Controller.RPM_STEPS.index(st.session_state.target_rpm)
    if idx < 5: st.session_state.target_rpm = Atom1Controller.RPM_STEPS[idx+1]
if col2.button("🔽 단계 내림 (Down)"):
    idx = Atom1Controller.RPM_STEPS.index(st.session_state.target_rpm)
    if idx > 1: st.session_state.target_rpm = Atom1Controller.RPM_STEPS[idx-1]

slope = st.sidebar.slider("경사도 (%)", 0, 15, 4)
rider_tq = st.sidebar.slider("탑승자 토크 (Nm)", 0, 15, 4)

# 물리 엔진 실행 및 자동 변속 로직 처리
bike = Atom1Controller()
state = bike.simulate_state(st.session_state.target_rpm, st.session_state.mode_idx, slope, rider_tq)

# 자동 변속 시뮬레이션 (상태가 안정화될 때까지 모드 변경)
for _ in range(5):
    if state['실제RPM'] <= st.session_state.target_rpm * 0.90:
        if st.session_state.mode_idx < 5: 
            st.session_state.mode_idx += 1
            state = bike.simulate_state(st.session_state.target_rpm, st.session_state.mode_idx, slope, rider_tq)
    elif state['실제RPM'] >= st.session_state.target_rpm * 1.10:
        if st.session_state.mode_idx > 0:
            st.session_state.mode_idx -= 1
            state = bike.simulate_state(st.session_state.target_rpm, st.session_state.mode_idx, slope, rider_tq)

# --- 결과 출력 ---
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("속도 (km/h)", f"{state['속도']}")
m2.metric("운전 모드", f"{state['모드']}")
m3.metric("공급 전류 (A)", f"{state['전류']} A")
m4.metric("대상 RPM", f"{st.session_state.target_rpm}")
m5.metric("실제 RPM", f"{state['실제RPM']}")

st.divider()

# --- 멀티 매핑 테이블 출력 (마커 이동 포함) ---
st.subheader("🗺️ 멀티 매핑 테이블")
st.write("현재 설정된 **대상 RPM**과 자동 변속된 **운전 모드**에 해당하는 셀이 붉은색으로 강조됩니다.")

# 데이터프레임 변환
tq_df = pd.DataFrame.from_dict(bike.WHEEL_TORQUE_MAP, orient='index')
curr_df = pd.DataFrame.from_dict(bike.CURRENT_MAP, orient='index')

# 활성화된 셀을 강조하기 위한 스타일 함수
def highlight_active_cell(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    map_rpm = state.get("매핑RPM", 0)
    active_mode = state.get("모드", "-")
    
    if map_rpm in styles.index and active_mode in styles.columns:
        # 현재 위치 셀의 배경색을 붉은색, 글씨를 흰색으로 변경
        styles.loc[map_rpm, active_mode] = 'background-color: #ff4b4b; color: white; font-weight: bold;'
    return styles

col_map1, col_map2 = st.columns(2)
with col_map1:
    st.markdown("##### ⚙️ 모터 토크 맵 (Nm)")
    # 스타일 적용된 데이터프레임 출력
    st.dataframe(tq_df.style.apply(highlight_active_cell, axis=None), use_container_width=True)

with col_map2:
    st.markdown("##### ⚡ 공급 전류 맵 (A)")
    st.dataframe(curr_df.style.apply(highlight_active_cell, axis=None), use_container_width=True)

st.divider()

# --- 토크 균형 그래프 ---
st.subheader("📊 토크 균형 (요구 vs 공급)")
chart_data = pd.DataFrame({
    "구분": ["요구 토크 (경사도 저항)", "공급 토크 (모터+라이더)"],
    "토크 (Nm)": [state['요구토크'], state['가용토크']]
})
st.bar_chart(chart_data.set_index("구분"), color=["#ff4b4b"])

if state['요구토크'] > state['가용토크']:
    st.warning(f"⚠️ 공급 토크가 부족하여 실제 RPM이 목표치보다 하락했습니다! (현재 모드: {state['모드']})")
else:
    st.success(f"✅ 공급 토크가 충분하여 대상 RPM을 안정적으로 유지/가속 중입니다.")

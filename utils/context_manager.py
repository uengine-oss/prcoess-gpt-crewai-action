from contextvars import ContextVar
from typing import Optional, Any
import json
import asyncio
import openai
from utils.logger import handle_error, log

todo_id_var: ContextVar[Optional[int]] = ContextVar('todo_id', default=None)
proc_id_var: ContextVar[Optional[str]] = ContextVar('proc_inst_id', default=None)

# ============================================================================
# 요약 처리
# ============================================================================

async def summarize_async(outputs: Any, feedbacks: Any, drafts: Any = None) -> tuple[str, str]:
    """LLM으로 컨텍스트 요약 - 병렬 처리로 별도 반환 (비동기)"""
    try:
        log("요약을 위한 LLM 병렬 호출 시작")
        
        # 데이터 준비
        outputs_str = _convert_to_string(outputs)
        feedbacks_str = _convert_to_string(feedbacks)
        
        # 병렬 처리
        output_summary, feedback_summary = await _summarize_parallel(outputs_str, feedbacks_str)
        
        log(f"이전결과 요약 완료: {len(output_summary)}자, 피드백 요약 완료: {len(feedback_summary)}자")
        return output_summary, feedback_summary
        
    except Exception as e:
        handle_error("요약처리", e)
        return "", ""

async def _summarize_parallel(outputs_str: str, feedbacks_str: str) -> tuple[str, str]:
    """병렬로 요약 처리 - 별도 반환"""
    tasks = []
    
    # 1. 이전 결과물 요약 태스크 (데이터가 있을 때만)
    if outputs_str and outputs_str.strip():
        output_prompt = _create_output_summary_prompt(outputs_str)
        tasks.append(_call_openai_api_async(output_prompt, "이전 결과물"))
    else:
        tasks.append(_create_empty_task(""))
    
    # 2. 피드백 요약 태스크 (데이터가 있을 때만)
    if feedbacks_str and feedbacks_str.strip():
        feedback_prompt = _create_feedback_summary_prompt(feedbacks_str)
        tasks.append(_call_openai_api_async(feedback_prompt, "피드백"))
    else:
        tasks.append(_create_empty_task(""))
    
    # 3. 두 태스크를 동시에 실행하고 완료될 때까지 대기
    output_summary, feedback_summary = await asyncio.gather(*tasks)
    
    # 4. 별도로 반환
    return output_summary, feedback_summary

async def _create_empty_task(result: str) -> str:
    """빈 태스크 생성 (즉시 완료)"""
    return result

def _convert_to_string(data: Any) -> str:
    """데이터를 문자열로 변환"""
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False)

def _create_output_summary_prompt(outputs_str: str) -> str:
    """이전 결과물 요약 프롬프트 - 상세 버전"""
    return f"""다음은 이전 작업에서 생성된 결과물입니다. 이를 체계적으로 분석하고 요약해주세요.

**이전 작업 결과물:**
{outputs_str}

**분석 및 요약 지침:**

1. **핵심 내용 파악:**
   - 수행된 주요 작업이나 업무는 무엇인가?
   - 달성한 목표나 완료된 단계는 무엇인가?
   - 생성된 결과물의 주요 특징은 무엇인가?

2. **구체적 데이터 추출:**
   - 수치, 날짜, 시간, 금액 등 구체적 정보
   - 개수, 크기, 비율 등 정량적 데이터
   - 이름, 제목, 파일명 등 고유 식별자

3. **중요 결과 및 성과:**
   - 완성된 문서, 코드, 디자인 등의 산출물
   - 해결된 문제나 개선된 사항
   - 검증된 결과나 테스트 성과

4. **현재 상태 및 진행도:**
   - 전체 프로젝트에서 현재 위치
   - 완료된 부분과 남은 작업
   - 다음 단계로 연결되는 요소

**요약 형식:**
📋 **이전 작업 결과 요약**

**🎯 주요 성과:**
• [핵심 달성 사항]
• [완료된 주요 작업]
• [생성된 핵심 결과물]

**📊 구체적 데이터:**
• [중요한 수치나 데이터]
• [날짜, 시간 등 구체적 정보]
• [정량적 성과 지표]

**📈 현재 진행 상황:**
• [완료된 단계]
• [현재 프로젝트 상태]
• [다음 단계 연결점]

**요약 원칙:**
- 객관적 사실만 기록하고 추측하지 않음
- 중요도 순으로 정리하되 누락 없이 포함
- 2000자 이내로 간결하되 핵심은 모두 포함
- 다음 작업자가 이해하기 쉽도록 명확하게 작성"""

def _create_feedback_summary_prompt(feedbacks_str: str) -> str:
    """피드백 요약 프롬프트 - 상세 버전"""
    return f"""다음은 이전 작업 결과에 대한 피드백입니다. 이를 체계적으로 분석하고 실행 가능한 요구사항으로 정리해주세요.

**피드백 내용:**
{feedbacks_str}

**분석 및 정리 지침:**

1. **피드백 유형 분류:**
   - 긍정적 평가: 만족스러운 부분, 잘된 점
   - 개선 요청: 수정이나 보완이 필요한 부분
   - 추가 요구: 새로운 기능이나 내용 추가 요청
   - 방향 변경: 접근 방식이나 전략의 변경 요구

2. **구체적 요구사항 추출:**
   - 명확한 지시사항이나 요청사항
   - 특정 수정이나 변경이 필요한 부분
   - 구체적인 기준이나 조건 제시
   - 일정이나 우선순위 관련 요구

3. **문제점 및 개선사항:**
   - 지적된 문제나 부족한 부분
   - 기대했던 것과 다른 결과
   - 품질이나 완성도 관련 이슈
   - 사용성이나 실용성 문제

4. **향후 작업 방향:**
   - 다음 단계에서 반영해야 할 사항
   - 전체적인 방향성 조정 필요성
   - 중점적으로 개선해야 할 영역
   - 추가 검토나 확인이 필요한 부분

**요약 형식:**
💬 **피드백 분석 요약**

**👍 긍정적 평가:**
• [잘된 점과 만족스러운 부분]
• [유지해야 할 요소]

**🔧 구체적 개선 요구:**
• [명확한 수정 지시사항]
• [추가해야 할 기능이나 내용]
• [변경이 필요한 접근 방식]

**⚠️ 주요 문제점:**
• [지적된 핵심 문제]
• [부족하거나 개선이 필요한 부분]
• [기대와 다른 결과]

**🎯 향후 작업 방향:**
• [다음 단계 우선순위]
• [중점 개선 영역]
• [전체적인 방향성 조정사항]

**실행 지침:**
- 각 피드백을 실행 가능한 액션 아이템으로 변환
- 우선순위와 중요도를 명확히 구분
- 모호한 표현을 구체적 요구사항으로 해석
- 2000자 이내로 간결하되 실행 가능하도록 구체적으로 작성"""


def _get_system_prompt() -> str:
    """상세한 시스템 프롬프트"""
    return """당신은 전문적인 프로젝트 분석 및 요약 전문가입니다.

**핵심 역할:**
- 복잡한 작업 결과물을 체계적으로 분석하고 핵심 정보를 추출
- 피드백을 실행 가능한 요구사항으로 변환하고 우선순위 설정
- 다음 작업자가 즉시 이해하고 활용할 수 있는 명확한 요약 제공

**분석 원칙:**
1. **객관성**: 주관적 해석을 배제하고 사실 기반으로 분석
2. **완전성**: 중요한 정보나 요구사항을 누락하지 않음
3. **구조화**: 정보를 논리적으로 분류하고 체계적으로 정리
4. **실용성**: 다음 단계 작업에 직접 활용 가능한 형태로 정리
5. **명확성**: 애매모호한 표현을 피하고 구체적으로 기술

**품질 기준:**
- 핵심 정보는 누락 없이 포함하되 불필요한 세부사항은 제외
- 수치, 날짜, 고유명사 등 구체적 데이터는 정확히 기록
- 요구사항은 실행 가능한 액션 아이템 형태로 변환
- 우선순위와 중요도를 명확히 구분하여 표시

**작업 지침:**
주어진 지침과 형식을 정확히 따르며, 지정된 글자 수 제한을 준수하세요.
모든 정보는 다음 작업 담당자가 이전 맥락을 완전히 이해할 수 있도록 충분히 상세하게 제공하되, 간결함을 유지하세요."""

async def _call_openai_api_async(prompt: str, task_name: str) -> str:
    """OpenAI API 병렬 호출"""
    try:
        # OpenAI 클라이언트를 async로 생성
        client = openai.AsyncOpenAI()
        
        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip()
        log(f"{task_name} 요약 완료: {len(result)}자")
        return result
        
    except Exception as e:
        handle_error(f"{task_name} OpenAI API 호출", e)
        return "요약 생성 실패"

def _call_openai_api(prompt: str) -> str:
    """OpenAI API 호출 (동기 버전 - 호환성 유지)"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": _get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        handle_error("OpenAI API 호출", e)
        return "요약 생성 실패"
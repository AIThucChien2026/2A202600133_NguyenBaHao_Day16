# 📋 KẾ HOẠCH TRIỂN KHAI — Lab 16: Reflexion Agent (LLM Thật)

> **Ngày tạo:** 2026-04-23  
> **Trạng thái:** 🟡 Chờ chọn LLM  
> **Mục tiêu:** 100/100 điểm (80 Core + 20 Bonus)

---

## 1. TỔNG QUAN BÀI LAB

### 1.1. Yêu cầu đề bài
Bài lab cung cấp một **scaffold Reflexion Agent** đang chạy bằng **mock data giả lập**. Nhiệm vụ của học viên:

| # | Yêu cầu | Trọng số |
|---|---------|----------|
| 1 | Thay thế mock → gọi **LLM thật** | Bắt buộc |
| 2 | Chạy benchmark trên **≥100 mẫu** HotpotQA | Bắt buộc |
| 3 | Xuất `report.json` + `report.md` đúng format | Bắt buộc |
| 4 | Tính **token thực tế** từ API response | Bắt buộc |
| 5 | Implement ≥1 Bonus extension | Tùy chọn (20đ) |

### 1.2. Cấu trúc dự án hiện tại

```
phase1-track3-lab1-advanced-agent/
├── run_benchmark.py              # ✅ Entry point
├── autograde.py                  # ✅ Chấm điểm tự động
├── requirements.txt              # ⚠️ Thiếu LLM SDK
├── data/
│   └── hotpot_mini.json          # ✅ 109 mẫu (đã đủ ≥100)
├── src/reflexion_lab/
│   ├── __init__.py               # ✅ OK
│   ├── schemas.py                # ❌ JudgeResult + ReflectionEntry trống
│   ├── prompts.py                # ❌ 3 prompts đều là placeholder
│   ├── mock_runtime.py           # ❌ Cần thay bằng LLM thật
│   ├── agents.py                 # ❌ Reflexion loop chưa implement
│   ├── reporting.py              # ⚠️ Cần cập nhật discussion/extensions
│   └── utils.py                  # ✅ OK
└── tests/
    └── test_utils.py             # ✅ OK
```

### 1.3. Tiêu chí chấm điểm (autograde.py)

#### Core Flow — 80 điểm

| Tiêu chí | Điểm | Điều kiện |
|----------|-------|-----------|
| Schema completeness | 30/30 | Report.json có đủ 6 keys: `meta`, `summary`, `failure_modes`, `examples`, `extensions`, `discussion` |
| Cả 2 agent chạy | 10/30 | `summary` chứa cả `"react"` và `"reflexion"` |
| ≥100 records | 10/30 | `meta.num_records >= 100` (109 mẫu × 2 agent = 218 records ✅) |
| ≥20 examples | 10/30 | `len(examples) >= 20` |
| ≥3 failure modes | 8/20 | `len(failure_modes) >= 3` |
| Discussion đủ dài | 12/20 | `len(discussion) >= 250` ký tự |

#### Bonus — 20 điểm (mỗi extension = 10đ, tối đa 20đ)

```
Recognized extensions:
  structured_evaluator    ← Evaluator trả JSON có cấu trúc
  reflection_memory       ← Lưu + sử dụng reflection qua các attempt
  benchmark_report_json   ← Xuất report.json
  mock_mode_for_autograding ← Giữ khả năng chạy mock
  adaptive_max_attempts   ← Điều chỉnh attempts theo difficulty
  memory_compression      ← Nén memory khi quá dài
  mini_lats_branching     ← Branching nhiều hướng giải
  plan_then_execute       ← Lập kế hoạch trước khi giải
```

---

## 2. DỰ TOÁN SỐ LƯỢNG LLM CALLS

### 2.1. Flow cho mỗi câu hỏi

```
┌─────────────────────────────────────────────────────────┐
│                   MỖI CÂU HỎI (1 example)              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ► ReAct Agent (1 attempt duy nhất):                    │
│    • 1× Actor call    → trả lời câu hỏi                │
│    • 1× Evaluator call → chấm điểm 0/1                 │
│    = 2 LLM calls                                        │
│                                                         │
│  ► Reflexion Agent (tối đa 3 attempts):                 │
│    Attempt 1:                                           │
│      • 1× Actor call                                   │
│      • 1× Evaluator call                               │
│      • (nếu sai) 1× Reflector call                     │
│    Attempt 2:                                           │
│      • 1× Actor call (có reflection memory)             │
│      • 1× Evaluator call                               │
│      • (nếu sai) 1× Reflector call                     │
│    Attempt 3:                                           │
│      • 1× Actor call (có reflection memory)             │
│      • 1× Evaluator call                               │
│    = 6-8 LLM calls (trung bình ~7)                      │
│                                                         │
│  TỔNG MỖI CÂU: ~9 LLM calls (trung bình)              │
└─────────────────────────────────────────────────────────┘
```

### 2.2. Tổng số calls cho 109 mẫu

| Thành phần | Calls/mẫu | × 109 mẫu | Tổng |
|------------|-----------|------------|------|
| ReAct Actor | 1 | 109 | 109 |
| ReAct Evaluator | 1 | 109 | 109 |
| Reflexion Actor | ~2.5 (TB) | 109 | ~273 |
| Reflexion Evaluator | ~2.5 (TB) | 109 | ~273 |
| Reflexion Reflector | ~1.5 (TB) | 109 | ~164 |
| **TỔNG** | | | **~928 calls** |

> **Ước tính:** ~900-1000 LLM API calls tổng cộng

### 2.3. Ước tính Token

Mỗi call trung bình:
- **Input:** ~300-500 tokens (prompt + context + memory)
- **Output:** ~50-150 tokens (answer/judge/reflection)

| Metric | Ước tính |
|--------|---------|
| Tổng input tokens | ~400K tokens |
| Tổng output tokens | ~100K tokens |
| **Tổng tokens** | **~500K tokens** |

---

## 3. LLM SỬ DỤNG (ĐÃ XÁC NHẬN ✅)

### 3.1. Hai model đã chọn

| # | Model ID chính xác | Vai trò trong project | Tốc độ | Chất lượng |
|---|-------------------|----------------------|--------|-----------|
| 1 | **`gemini-3.1-flash-lite-preview`** | **Actor** (trả lời câu hỏi) | ⚡ Rất nhanh | ✅ Tốt cho trả lời nhanh |
| 2 | **`gemma-3-27b-it`** | **Evaluator** (chấm điểm) + **Reflector** (đề xuất chiến thuật) | 🟡 Trung bình | ⭐ Mạnh reasoning, đánh giá chính xác |

### 3.2. Chiến lược phân vai trò

```
┌──────────────────────────────────────────────────────────────┐
│                     PHÂN VAI TRÒ 2 MODEL                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  gemini-3.1-flash-lite-preview (nhanh + rẻ)                 │
│  └── Actor:      Đọc context → trả lời câu hỏi             │
│      → ~382 calls (ReAct: 109 + Reflexion: ~273)            │
│      → Cần nhanh vì gọi nhiều lần nhất                      │
│                                                              │
│  gemma-3-27b-it (mạnh reasoning)                             │
│  ├── Evaluator:  So sánh answer vs gold → chấm 0/1          │
│  │   → ~382 calls                                            │
│  │   → Cần chính xác để đánh giá đúng/sai                   │
│  └── Reflector:  Phân tích lỗi → rút bài học → chiến thuật  │
│      → ~164 calls                                            │
│      → Cần reasoning tốt để reflection chất lượng           │
│                                                              │
│  TỔNG: ~928 calls                                            │
│    • flash-lite: ~382 calls (41%)                            │
│    • gemma-27b:  ~546 calls (59%)                            │
└──────────────────────────────────────────────────────────────┘
```

**Lý do phân vai:**
- **Actor** chỉ cần đọc context và trả lời ngắn → `flash-lite` đủ tốt, lại nhanh
- **Evaluator** cần đánh giá chính xác đúng/sai → `gemma-27b` reasoning mạnh hơn, tránh chấm nhầm
- **Reflector** cần phân tích sâu tại sao sai, đề xuất chiến thuật mới → `gemma-27b` phù hợp

### 3.3. Thông tin kỹ thuật

| Thuộc tính | Giá trị |
|-----------|---------|
| **SDK** | `google-genai` (package mới nhất) |
| **Cài đặt** | `pip install google-genai` |
| **API Key** | Dùng chung 1 key `GEMINI_API_KEY` từ Google AI Studio |
| **Token count** | `response.usage_metadata.prompt_token_count` + `candidates_token_count` |
| **Free tier** | ~1500 req/ngày (đủ cho ~928 calls) |

**Code mẫu gọi API:**
```python
from google import genai
import os

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Actor → flash-lite (nhanh, trả lời câu hỏi)
response = client.models.generate_content(
    model="gemini-3.1-flash-lite-preview",
    contents="..."
)

# Evaluator + Reflector → gemma-3-27b-it (chấm điểm + phân tích lỗi)
response = client.models.generate_content(
    model="gemma-3-27b-it",
    contents="..."
)
```

### 3.4. Lựa chọn đã xác nhận

```
┌─────────────────────────────────────────────────────┐
│  ✅ ĐÃ XÁC NHẬN                                    │
│                                                     │
│  Model 1: gemini-3.1-flash-lite-preview             │
│           → Actor (trả lời câu hỏi)                │
│                                                     │
│  Model 2: gemma-3-27b-it                            │
│           → Evaluator (chấm điểm)                  │
│           → Reflector (phân tích + chiến thuật)     │
│                                                     │
│  SDK:     google-genai                              │
│  API Key: GEMINI_API_KEY (từ .env)                  │
└─────────────────────────────────────────────────────┘
```

---

## 4. CÁC BƯỚC THỰC HIỆN CHI TIẾT

### Step 1 — Hoàn thiện `schemas.py` (Data Models)

**File:** `src/reflexion_lab/schemas.py`  
**Thời gian:** ~5 phút

**Hiện tại:** `JudgeResult` và `ReflectionEntry` đang trống (`pass`)

**Cần làm:**

```python
# JudgeResult - kết quả đánh giá từ Evaluator
class JudgeResult(BaseModel):
    score: int          # 1 = đúng, 0 = sai
    reason: str         # Lý do cho điểm
    missing_evidence: list[str] = Field(default_factory=list)   # Bằng chứng thiếu
    spurious_claims: list[str] = Field(default_factory=list)    # Thông tin sai

# ReflectionEntry - một mục phản chiếu
class ReflectionEntry(BaseModel):
    attempt_id: int         # Lần thử thứ mấy
    failure_reason: str     # Lý do sai
    lesson: str             # Bài học rút ra
    next_strategy: str      # Chiến thuật cho lần sau
```

**Tại sao biết cần các field này?**  
→ File `mock_runtime.py` (line 19-26) đã sử dụng chúng, chứng tỏ đây là cấu trúc mong muốn.

---

### Step 2 — Viết System Prompts (`prompts.py`)

**File:** `src/reflexion_lab/prompts.py`  
**Thời gian:** ~15 phút

**Hiện tại:** 3 prompt đều là `[TODO]` placeholder

**Cần viết 3 prompts:**

#### 2.1. ACTOR_SYSTEM
Nhiệm vụ: Hướng dẫn LLM trả lời câu hỏi multi-hop
- Đọc context được cung cấp
- Suy luận qua nhiều bước (multi-hop)
- Nếu có reflection memory → sử dụng chiến thuật mới
- Chỉ trả lời câu trả lời ngắn gọn, không giải thích

#### 2.2. EVALUATOR_SYSTEM
Nhiệm vụ: Chấm điểm câu trả lời
- So sánh predicted answer với gold answer
- Cho điểm 0 hoặc 1
- Trả về JSON: `{"score": 0|1, "reason": "...", "missing_evidence": [...], "spurious_claims": [...]}`

#### 2.3. REFLECTOR_SYSTEM
Nhiệm vụ: Phân tích lỗi và đề xuất chiến thuật
- Phân tích tại sao câu trả lời sai
- Rút ra bài học
- Đề xuất chiến thuật mới
- Trả về JSON: `{"attempt_id": N, "failure_reason": "...", "lesson": "...", "next_strategy": "..."}`

---

### Step 3 — Tạo `llm_runtime.py` (Thay thế mock)

**File:** `src/reflexion_lab/llm_runtime.py` **(FILE MỚI)**  
**Thời gian:** ~30 phút

Đây là bước **quan trọng nhất**. Tạo file mới với 3 hàm **cùng signature** với `mock_runtime.py`:

```
llm_runtime.py
├── _call_llm(system_prompt, user_prompt)  ← Hàm gọi API chung
│   └── Returns: (text_response, token_count, latency_ms)
│
├── actor_answer(example, attempt_id, agent_type, reflection_memory)
│   ├── Build prompt từ: question + context + reflection_memory
│   ├── Gọi _call_llm() với ACTOR_SYSTEM
│   └── Returns: (answer_str, token_count, latency_ms)
│
├── evaluator(example, answer)
│   ├── Build prompt từ: question + gold_answer + predicted_answer
│   ├── Gọi _call_llm() với EVALUATOR_SYSTEM
│   ├── Parse JSON response → JudgeResult
│   └── Returns: (JudgeResult, token_count, latency_ms)
│
└── reflector(example, attempt_id, judge)
    ├── Build prompt từ: question + answer + judge.reason
    ├── Gọi _call_llm() với REFLECTOR_SYSTEM
    ├── Parse JSON response → ReflectionEntry
    └── Returns: (ReflectionEntry, token_count, latency_ms)
```

**Yêu cầu kỹ thuật:**
- Đọc API key từ `.env` (dùng `python-dotenv`)
- Đo **token thực tế** từ API response metadata
- Đo **latency thực tế** bằng `time.perf_counter()`
- Xử lý error: retry, timeout, rate limit
- Parse JSON response an toàn (có fallback nếu LLM trả format sai)

---

### Step 4 — Hoàn thiện logic Reflexion trong `agents.py`

**File:** `src/reflexion_lab/agents.py`  
**Thời gian:** ~20 phút

**4 thay đổi chính:**

#### 4.1. Đổi import source
```python
# TRƯỚC (mock):
from .mock_runtime import FAILURE_MODE_BY_QID, actor_answer, evaluator, reflector

# SAU (LLM thật):
from .llm_runtime import actor_answer, evaluator, reflector
```

#### 4.2. Cập nhật hàm `run()` — nhận token/latency thực
```python
# TRƯỚC:
answer = actor_answer(example, attempt_id, self.agent_type, reflection_memory)
judge = evaluator(example, answer)
token_estimate = 320 + (attempt_id * 65) + ...  # hardcoded ❌
latency_ms = 160 + (attempt_id * 40) + ...      # hardcoded ❌

# SAU:
answer, actor_tokens, actor_latency = actor_answer(example, attempt_id, self.agent_type, reflection_memory)
judge, eval_tokens, eval_latency = evaluator(example, answer)
token_estimate = actor_tokens + eval_tokens      # thực tế ✅
latency_ms = actor_latency + eval_latency        # thực tế ✅
```

#### 4.3. Hoàn thiện reflection loop (line 31-35)
```python
# TRƯỚC:
# TODO: Học viên triển khai logic Reflexion tại đây
pass

# SAU:
if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
    ref, ref_tokens, ref_latency = reflector(example, attempt_id, judge)
    trace.reflection = ref
    reflections.append(ref)
    reflection_memory.append(ref.next_strategy)
    token_estimate += ref_tokens
    latency_ms += ref_latency
```

#### 4.4. Xác định failure_mode bằng LLM (thay vì lookup dict)
```python
# TRƯỚC:
failure_mode = "none" if final_score == 1 else FAILURE_MODE_BY_QID.get(example.qid, "wrong_final_answer")

# SAU: Phân loại dựa trên nội dung judge.reason
failure_mode = "none" if final_score == 1 else classify_failure(judge.reason)
```

---

### Step 5 — Cập nhật `requirements.txt`

**File:** `requirements.txt`  
**Thời gian:** ~2 phút

Thêm LLM SDK tùy theo lựa chọn:

```
# Nếu chọn Gemini:
google-generativeai>=0.8

# Nếu chọn OpenAI:
openai>=1.30

# Nếu chọn Ollama:
ollama>=0.3
```

---

### Step 6 — Cập nhật `run_benchmark.py` + `reporting.py`

**File:** `run_benchmark.py`  
**Thời gian:** ~10 phút

Thay đổi:
- `mode="mock"` → `mode="real"`
- Thêm `rich.progress.Progress` để theo dõi tiến trình (109 mẫu × 2 agent)
- Thêm `try/except` cho từng example (tránh 1 lỗi API crash toàn bộ)
- Load `.env` bằng `dotenv.load_dotenv()`

**File:** `src/reflexion_lab/reporting.py`  
**Thời gian:** ~10 phút

Thay đổi:
- Viết `discussion` thật (≥250 ký tự) — phân tích kết quả ReAct vs Reflexion
- Đảm bảo `extensions` list chứa các bonus đã implement

---

### Step 7 — Triển khai Bonus Features

**Thời gian:** ~20 phút

#### 7.1. `adaptive_max_attempts` (10 điểm)

Điều chỉnh số lần thử tối đa theo độ khó câu hỏi:

```python
class ReflexionAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_type="reflexion", max_attempts=3)
    
    def run(self, example):
        # Override max_attempts theo difficulty
        self.max_attempts = {"easy": 1, "medium": 3, "hard": 5}[example.difficulty]
        return super().run(example)
```

**Lý do:** Câu easy không cần retry, câu hard cần nhiều cơ hội hơn.

#### 7.2. `memory_compression` (10 điểm)

Nén reflection memory khi quá dài để tránh vượt context window:

```python
def compress_memory(memory: list[str], max_items: int = 3) -> list[str]:
    """Giữ tối đa max_items mục gần nhất, tóm tắt các mục cũ"""
    if len(memory) <= max_items:
        return memory
    old = memory[:-max_items]
    recent = memory[-max_items:]
    summary = "Previous strategies tried: " + "; ".join(old)
    return [summary] + recent
```

---

## 5. TỔNG HỢP FILES CẦN THAY ĐỔI

| # | File | Hành động | Mô tả |
|---|------|-----------|-------|
| 1 | `src/reflexion_lab/schemas.py` | MODIFY | Thêm fields cho JudgeResult + ReflectionEntry |
| 2 | `src/reflexion_lab/prompts.py` | MODIFY | Viết 3 system prompts hoàn chỉnh |
| 3 | `src/reflexion_lab/llm_runtime.py` | **NEW** | Runtime gọi LLM thật, đo token + latency |
| 4 | `src/reflexion_lab/agents.py` | MODIFY | Import LLM runtime, hoàn thiện reflexion loop, token thực |
| 5 | `requirements.txt` | MODIFY | Thêm LLM SDK |
| 6 | `run_benchmark.py` | MODIFY | mode=real, progress bar, error handling |
| 7 | `src/reflexion_lab/reporting.py` | MODIFY | Discussion thật, extensions list |
| 8 | `.env` | **NEW** | API key |

**Files KHÔNG thay đổi:**
- `autograde.py` ← Không được sửa
- `data/hotpot_mini.json` ← Đã đủ 109 mẫu
- `src/reflexion_lab/utils.py` ← Đã hoàn thiện
- `src/reflexion_lab/mock_runtime.py` ← Giữ nguyên (có thể dùng cho mock mode)

---

## 6. THỨ TỰ THỰC HIỆN + CHECKPOINT

```
Step 1: schemas.py ──────────► Checkpoint: Import & tạo instance OK
                                  │
Step 2: prompts.py ──────────► Checkpoint: 3 prompts đã viết
                                  │
Step 3: llm_runtime.py ──────► Checkpoint: Test 1 câu hỏi → LLM trả lời đúng
                                  │
Step 4: agents.py ───────────► Checkpoint: Chạy 5 mẫu OK → report mini
                                  │
Step 5: requirements.txt ───► Checkpoint: pip install OK
                                  │
Step 6: run_benchmark + report ► Checkpoint: Chạy 109 mẫu → report.json OK
                                  │
Step 7: Bonus features ─────► Checkpoint: autograde.py → 100/100
```

---

## 7. VERIFICATION — KIỂM TRA KẾT QUẢ

### 7.1. Chạy benchmark
```bash
python run_benchmark.py --dataset data/hotpot_mini.json --out-dir outputs/real_run
```

### 7.2. Kiểm tra output
```bash
# Kiểm tra file tồn tại
ls outputs/real_run/
# → report.json, report.md, react_runs.jsonl, reflexion_runs.jsonl

# Kiểm tra num_records
python -c "import json; d=json.load(open('outputs/real_run/report.json')); print(d['meta']['num_records'])"
# → Phải >= 100
```

### 7.3. Chạy autograde
```bash
python autograde.py --report-path outputs/real_run/report.json
```

**Kết quả mong đợi:**
```
Auto-grade total: 100/100
- Flow Score (Core): 80/80
  * Schema: 30/30
  * Experiment: 30/30
  * Analysis: 20/20
- Bonus Score: 20/20
```

---

## 8. RỦI RO VÀ CÁCH XỬ LÝ

| Rủi ro | Xác suất | Giải pháp |
|--------|----------|-----------|
| Rate limit API | Trung bình | Thêm `time.sleep(0.5)` giữa mỗi call, retry logic |
| LLM trả format JSON sai | Cao | Regex fallback + try/except parse |
| LLM trả lời dài thay vì ngắn | Trung bình | Prompt rõ ràng + post-process cắt ngắn |
| API key hết quota | Thấp | Gemini free tier = 1500 req/ngày (đủ dùng) |
| Timeout request | Thấp | Set timeout 30s + retry 2 lần |

---

## ✏️ GHI CHÚ CỦA HỌC VIÊN

```
LLM đã chọn:      _________________________
Model cụ thể:     _________________________
API Key status:   ☐ Đã có  |  ☐ Cần tạo
Ghi chú thêm:     _________________________
```

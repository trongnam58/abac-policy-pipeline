# ABAC contextual policy formalization — W1 + W2

Pipeline: **NLPS (VI/EN) → JSON → mô hình UML (.puml/.use) → bất biến OCL**.

Trạng thái hiện tại:
- **W1** ✅ khung chạy được: rules tiếng Anh, schema JSON, sinh `.puml`, khung `.use`,
  bất biến OCL theo 3 mẫu IP, kiểm tra nhẹ.
- **W2** ✅ rules tiếng Việt, nhánh LLM (prompt few-shot + client OpenAI-compatible +
  gộp hybrid), gold 20 câu, runner ablation 3 cấu hình.
- **W3–W4** ⬜ dữ liệu 200 câu + gán nhãn độc lập, validate `.use` bằng USE,
  demo Streamlit, đóng gói.

## Chạy nhanh

```bash
python run_all.py --input data/vact_en_sample.txt --out out
python run_all.py --input data/vact_vi_sample.txt --out out_vi   # tiếng Việt
```

Kết quả trong `out/`: `policies.json`, `models/policy_*.puml`, `models/policies.use`,
`ocl/policy_*.ocl`, `ocl/policies.ocl`.

Đo P/R/F1 và ablation:

```bash
python scripts/run_ablation.py --input data/vact_en_sample.txt --gold data/gold_sample.json
```

## Bật nhánh LLM (W2)

Client dùng giao diện OpenAI-compatible (`/chat/completions`), chạy được với
OpenAI, Groq, hoặc model local (Ollama/vLLM):

```bash
export ABAC_LLM_ENDPOINT="https://api.openai.com/v1"   # hoặc http://localhost:11434/v1
export ABAC_LLM_MODEL="gpt-4o-mini"                    # hoặc qwen2.5:7b, llama3.1
export ABAC_LLM_API_KEY="..."                          # model local có thể bỏ trống
```

Sau đó chạy `run_all.py --llm-mode hybrid` (rules + LLM) hoặc `--llm-mode llm`
(chỉ LLM, dùng cho ablation). Không cấu hình endpoint thì hai chế độ này tự bỏ qua
hoặc chỉ chạy rules — `run_ablation.py` ghi rõ lý do "skipped" trong summary.

## Kết quả W2 (20 câu gold nội bộ)

| Cấu hình | micro F1 | subject | action | resource | environment |
|---|---|---|---|---|---|
| rules EN | 0.988 | 1.000 | 1.000 | 0.941 | 1.000 |
| rules VI | 0.988 | 1.000 | 1.000 | 0.941 | 1.000 |
| hybrid | — | — | — | — | — (chờ endpoint) |
| llm | — | — | — | — | — (chờ endpoint) |

Lưu ý trung thực: gold 20 câu do nhóm gán ở W2 để chốt khung đo; **số liệu chính
thức phải dùng gold 200 câu gán độc lập** (W3). Lỗi còn lại của rules: câu có hai
tài nguyên (id-6 "cập nhật điểm" và "gán điểm cuối kỳ") — baseline chọn tài nguyên
xuất hiện sớm nhất.

## Cấu trúc

```text
src/abac/
  schema.py                 # dataclass Policy/Subject/Action/... + JSON I/O
  extraction/
    rules.py                # điều phối EN + nhận diện ngôn ngữ
    vi_rules.py             # luật tiếng Việt (W2)
    prompts.py              # prompt few-shot + schema hint
    client.py               # client OpenAI-compatible + parse JSON
    llm.py                  # cấu hình, gộp hybrid, xử lý lỗi
    pipeline.py             # rules / hybrid / llm + thống kê
  modeling/
    metamodel.py            # 9 lớp + 11 enum
    puml.py                 # sinh .puml
    use_model.py            # sinh khung .use
  ocl/
    patterns.py             # 3 mẫu IP
    generator.py            # sinh bất biến
    validator.py            # kiểm tra nhẹ
  evaluation/metrics.py     # P/R/F1 theo thành phần
scripts/run_ablation.py     # ablation rules / hybrid / llm
data/
  vact_en_sample.txt        # 20 câu EN
  vact_vi_sample.txt        # 20 câu VI (cặp với EN)
  gold_sample.json          # gold 20 câu (W2, sẽ thay bằng gold 200 câu W3)
docs/schema.md
tests/test_smoke.py         # 8 smoke test
```

## Ghi chú kỹ thuật

- Không cần thư viện ngoài (Python ≥ 3.10, stdlib). Pydantic/Jinja2/spaCy là tùy chọn.
- `validator.py` là bộ lọc nhẹ; kiểm chứng chính thức bằng **USE headless** ở W3.
- LLM chỉ nên gọi cho câu khó; hybrid hiện gọi cho mọi câu — W3 sẽ thêm bộ chọn câu
  (rules trả thiếu thành phần hoặc câu có mẫu phủ định/mệnh đề ghép) để giảm chi phí.

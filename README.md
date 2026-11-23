# ABAC contextual policy formalization

Hiện thực khung 3 mô-đun của bài báo *"A Model-Driven Engineering-Based Framework for
Formalizing Contextual ABAC Policies from Natural Language Policy Statements"*:

**NLPS (EN/VI) → thành phần chính sách (JSON) → mô hình biểu diễn UML/USE → bất biến OCL**

## Đối chiếu với bài báo

| Bài báo | Hiện thực | File |
|---|---|---|
| Mô-đun 1, Fig. 1: gazetteer + trigger phrase + POS tagging (spaCy) | luật EN/VI; spaCy `en_core_web_md` + EntityRuler (tuỳ chọn, rơi về regex nếu chưa cài) | `extraction/rules.py`, `vi_rules.py`, `nlp.py`, `common.py` |
| Điều kiện ngữ cảnh (`for_courses_that_they_are_taking`, `not_in_the_academic_affairs_office`…) | `Condition.normalized` → `consideredContext` | `extraction/common.py` |
| Ràng buộc thời gian/thời lượng | khung giờ → `timeInPoint`; "more than 560 hours per year" → `duration > 560`, `durationUnit=#hours` | `common.detect_duration` |
| Fig. 4: siêu mô hình (9 lớp + associationclass `Context` + 11 enum) | đầy đủ thuộc tính và liên kết | `modeling/metamodel.py` |
| Mô-đun 2: biến đổi siêu mô hình → mô hình biểu diễn (mục 3.1) | tự động: lớp tài nguyên thay `ObjectType`, bỏ `SubjectType`/`otherAttributes`, enum `Role`/`Network`/`ORG` từ dữ liệu, `<OP>executed` trong `Action` | `modeling/use_model.py` |
| Fig. 8: sơ đồ mô hình biểu diễn | `models/model.puml` (+ `.use`, `.soil`) | `modeling/puml.py` |
| Fig. 5–7: 3 mẫu IP | `ContextualUser`, `ContextualUserObjectType`, `ContextualUserRestricted` (+ mẫu mở rộng `ContextualUserCardinality`, xem dưới) | `ocl/patterns.py` |
| Fig. 3: selectIP, determineOCLoperator, determineLogicalOperator, formOCLinvariant | đúng các bước | `ocl/generator.py` |
| Kiểm chứng bằng USE | `--use-check` (biên dịch + `check`), `--semantic-check` (kiểm thử ngữ nghĩa từng chính sách) | `ocl/use_runner.py`, `ocl/validator.py` |
| Dataset VACT (100 câu) | `data/vact_en.txt` — lấy nguyên văn từ repo dataset bài báo trích dẫn [26] (https://github.com/nhatanh19-git/ABAC); repo đó chưa ghi giấy phép | |

Mở rộng ngoài bài báo (các hướng phát triển ở mục 6 của bài báo):
- luật tiếng Việt + `data/vact_vi.txt` (bản dịch nháp 100 câu, khớp từng dòng với bản EN);
- nhánh LLM/hybrid;
- mẫu IP thứ tư `ContextualUserCardinality` cho ràng buộc đếm ("register for at most one
  graduation project topic" → `u.subject.actions.objects.graduation_project_topic->size() > 1
  implies … REGISTERexecuted=false`);
- kiểm thử ngữ nghĩa từng chính sách bằng USE;
- demo giao diện (`app.py`).

Ba câu ví dụ trong bài báo (id-11, id-46, id-88) sinh ra OCL trùng với test1–test4 ở mục 4.2
(kể cả tên vai trò `agreement`). Xem `tests/test_paper_examples.py`.

## Cài đặt

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m spacy download en_core_web_md
```

Lõi pipeline chạy được với Python ≥ 3.10 thuần (không spaCy thì dùng regex tương đương;
đặt `ABAC_DISABLE_SPACY=1` để ép chế độ này).

## Chạy

```bash
python run_all.py --input data/vact_en.txt --out out            # 100 câu VACT
python run_all.py --input data/vact_vi.txt --out out_vi         # tiếng Việt (100 câu)
streamlit run app.py                                             # demo giao diện
```

Đầu ra trong `out/`:

| File | Nội dung |
|---|---|
| `policies.json` | thành phần chính sách (mô-đun 1) — schema: `docs/schema.md` |
| `models/policies.use` | mô hình biểu diễn + khối `constraints` (mô-đun 2 + 3) |
| `models/policies.soil` | thể hiện (object diagram) để USE `check` |
| `models/model.puml`, `models/policy_*.puml` | sơ đồ lớp / sơ đồ thể hiện từng câu |
| `ocl/policy_*.ocl`, `ocl/policies.ocl` | bất biến OCL |

### Kiểm chứng bằng USE

Tải USE (https://github.com/useocl/use/releases, cần Java 21+), rồi:

```bash
export ABAC_USE_HOME=/path/to/use-7.5.0
python run_all.py --input data/vact_en.txt --out out --use-check
```

`--use-check` chạy `use -c policies.use` (parse + type-check đặc tả và OCL), sau đó nạp
`policies.soil` và chạy `check`.

`--semantic-check` kiểm thử ngữ nghĩa từng chính sách: với mỗi chính sách (và mỗi nhóm chủ
thể), sinh `out/semantic/policy_<id>.use` chỉ chứa bất biến của nó cùng kịch bản 2 trạng thái —
trạng thái **tuân thủ** (vế trái của bất biến đúng, `<OP>executed` đúng như chính sách) phải
cho 0 failures; sau `reset`, trạng thái **vi phạm** (đảo `<OP>executed`) phải làm mọi bất biến
FAILED. Như vậy mỗi bất biến được chứng minh là không đúng hiển nhiên và bắt được vi phạm.

Các test USE (`test_use_*`) tự chạy khi có `ABAC_USE_HOME`.

### Đo P/R/F1 và ablation

```bash
python scripts/run_ablation.py --input data/vact_en_sample.txt --gold data/gold_sample.json
```

Nhánh LLM: đặt `ABAC_LLM_ENDPOINT`, `ABAC_LLM_MODEL`, `ABAC_LLM_API_KEY` (giao diện
OpenAI-compatible) rồi chạy `run_all.py --llm-mode hybrid|llm`.

### Kiểm thử

```bash
.venv/Scripts/python -m pytest --cov=src/abac      # 60 test (7 test USE tự bỏ qua nếu chưa cài), độ phủ ~93%
python tests/test_smoke.py                          # smoke test, chỉ cần stdlib
```

CI (`.github/workflows/tests.yml`): job `stdlib` (Python 3.10, không spaCy) và job `full`
(spaCy + Java 21 + USE 7.5.0, chạy cả `--use-check --semantic-check`).

## Kết quả hiện tại

Trên 100 câu VACT: 142 bất biến OCL (chế độ spaCy) — `ContextualUser` 110,
`ContextualUserObjectType` 28, `ContextualUserCardinality` 2, `ContextualUserRestricted` 2;
100% qua kiểm tra cú pháp + ngữ nghĩa với mô hình. Câu id-75 ("A graduation project can have
at most two instructors" — không có chủ thể/hành động) không sinh bất biến.

Kiểm chứng bằng USE 7.5.0 (Java 21), cho cả bản EN và bản VI:
- `use -c policies.use`: không lỗi parse/type-check cho toàn bộ đặc tả và 142 bất biến;
- `check` trên `policies.soil`: 0 failures, không vi phạm bội số;
- `--semantic-check`: **98/98 chính sách (103 trường hợp)** đạt — trạng thái tuân thủ 0
  failures, trạng thái vi phạm làm mọi bất biến FAILED.

Bản dịch tiếng Việt (`data/vact_vi.txt`): trích xuất trùng với bản EN trên cả 4 thành phần
(micro F1 1.0 khi lấy kết quả EN làm tham chiếu). Bản dịch do máy soạn theo thuật ngữ của
luật VI nên con số này lạc quan; câu tiếng Việt viết tự nhiên sẽ cho kết quả thấp hơn.

Gold 20 câu nội bộ (`data/gold_sample.json`): micro F1 0.970 (subject 1.000, action 0.980,
resource 0.889, environment 1.000). Phần chênh nằm ở cách gán nhãn: gold không ghi
tài nguyên cho "register for courses" (pipeline: `course`) và không ghi hành động cho
"class schedules are only allowed …" (pipeline: READ ngầm định).

### Trên gold của nhóm tác giả (`result/VACT_final/policy_dataset_gold.json`, repo [26])

```bash
python scripts/eval_authors_gold.py --gold <gold.json> --authors-machine <policy_dataset.json>
```

Hai file này không đưa vào repo (repo gốc không có giấy phép). Cùng một phép ánh xạ
schema (`evaluation/external_gold.py`) cho cả hai nguồn:

| | subject | action | object | environment | condition | micro (4 trường) | micro (5 trường) |
|---|---|---|---|---|---|---|---|
| Pipeline này | 0.946 | 0.914 | 0.579 | 0.856 | 0.729 | **0.832** | 0.819 |
| Output máy của tác giả | 0.962 | 1.000 | 0.950 | 0.995 | 0.756 | 0.979 | 0.945 |

Lưu ý khi đọc bảng:
- 52/100 bản ghi gold giống hệt output máy của tác giả (gold phần lớn là output máy chưa
  sửa), nên điểm của chính máy tác giả bị thổi phồng.
- Gold sai nhãn rõ ràng ở nhiều chỗ: 28 câu ghi tài nguyên là phòng ban/hệ thống
  (`affairs_office`, `academic_affairs`, `learning_management_system`…); bỏ 28 câu này thì
  object F1 của pipeline khoảng 0.81. Gold cũng bỏ sót động từ thứ hai ("upload and download"
  chỉ ghi UPLOAD) và gán nhiều điều kiện "if …" thành `location`.
- Script `compute_fscore.py` của tác giả đọc khoá `subject`/`object`/`environment`, trong
  khi gold dùng `subjects`/`resource`/`environments` (khoá `environment` vắng ở cả 100 bản
  ghi), nên không tái lập được con số 0.84/0.85/0.84 của bài báo từ các file đã công bố.

## Giới hạn còn lại

- **Chưa có gold gán độc lập, chất lượng tốt.** Gold của tác giả (ở trên) có nhiều nhãn
  sai; cần người gán nhãn độc lập theo `docs/schema.md` để có số liệu đáng tin.
- **Hạn chế của mẫu IP trong bài báo**: vế `User.allInstances()->forAll(u | u.roleActivated=#X …)`
  chỉ đúng khi *mọi* người dùng trong hệ thống có vai trò X. Trong trạng thái có nhiều người
  dùng với vai trò khác nhau, vế trái sai và bất biến đúng hiển nhiên (không bắt được vi
  phạm). Vì vậy `check` trên `policies.soil` (gộp 100 câu) chỉ xác nhận thể hiện khớp mô
  hình; `--semantic-check` kiểm từng chính sách trên trạng thái riêng (mỗi nhóm chủ thể một
  trạng thái). Đề xuất cải tiến mẫu: dùng `exists`/điều hướng từ `actions.subjects.user`
  thay cho `User.allInstances()->forAll`.
- Luật trích xuất vẫn dựa trên gazetteer/trigger phrase (giới hạn giống bài báo).
  Ràng buộc đếm trên tài nguyên không gắn với hành động của người dùng (id-75) và ràng buộc
  không gian (SpatialConstraint, LOC/FAC/GPE, Device — VACT không có câu nào) chưa được
  hình thức hoá.
- Nhánh LLM chưa có số liệu (cần endpoint). CI chưa được chạy trên GitHub.
- `determineLogicalOperator`: `or` chỉ dùng cho các lựa chọn thay thế của chủ thể/mạng
  (được bọc ngoặc); các nhóm thuộc tính còn lại nối bằng `and`.

## Giấy phép

MIT (xem `LICENSE`).

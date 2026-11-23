# Schema JSON trung gian (`out/policies.json`)

Một dataset gồm danh sách policy; mỗi policy tương ứng một câu NLPS.

## PolicyDataset

| Trường | Kiểu | Ghi chú |
|---|---|---|
| domain | string | miền dữ liệu, mặc định `education` |
| source | string | nguồn, mặc định `vact` |
| policies | list[Policy] | danh sách chính sách |

## Policy

| Trường | Kiểu | Ghi chú |
|---|---|---|
| id | int | số thứ tự |
| sentence | string | câu gốc (VI/EN) |
| decision | `permit` \| `deny` | quyết định uỷ quyền |
| modality | string | `can`, `cannot`, `can only` |
| subjects | list[Subject] | chủ thể (1–2) |
| actions | list[Action] | hành động kèm toán tử chuẩn hoá |
| resource | Resource? | đối tượng/tài nguyên |
| environments | list[Environment] | ngữ cảnh mạng/thời gian/… |
| conditions | list[Condition] | điều kiện ngữ cảnh (scope, subject_scope, if, only if, after, approval…) |
| logical_operator | `and` \| `or` | toán tử logic nối các lựa chọn thay thế (vd. "academic affairs or finance office") |

## Subject / Action / Resource / Environment / Condition

| Lớp | Trường |
|---|---|
| Subject | role, entity_type, membership?, position? |
| Action | verb, operation (`READ`, `UPLOAD`, `DOWNLOAD`, `NUMBER`…) |
| Resource | label, entity_type, attributes (`{"level": "department"}`), count_operator? + count? (ràng buộc đếm, vd. "at most one" → `<=`, 1) |
| Environment | id, env_type (`network`/`temporal`/`duration`), namespace?, trigger_phrase?, time_from?, time_to?, raw?, operator? (`<`,`<=`,`=`,`<>`,`>`,`>=`), value?, unit? (TimeUnit), period? |
| Condition | text, kind (`scope`/`subject_scope`/`condition`/`restriction`/`approval`/`precondition`), normalized (dùng cho `consideredContext`) |

## Ví dụ rút gọn

```json
{
  "domain": "education",
  "source": "vact",
  "policies": [
    {
      "id": 1,
      "sentence": "Civilian students can view rosters in the learning management system.",
      "decision": "permit",
      "modality": "can",
      "subjects": [{"role": "student", "entity_type": "user", "membership": "civilian"}],
      "actions": [{"verb": "view", "operation": "READ"}],
      "resource": {"label": "rosters", "entity_type": "roster"},
      "environments": [{"id": "env_1", "env_type": "network",
                        "namespace": "learning_management_system"}],
      "conditions": []
    }
  ]
}
```

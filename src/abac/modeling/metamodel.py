# -*- coding: utf-8 -*-
"""Siêu mô hình ABAC theo ngữ cảnh (Fig. 4 của bài báo).

9 lớp UML thông thường + associationclass "Context" (giữa Action và Environment)
và 11 kiểu liệt kê. Mô-đun 2 (use_model.py) biến đổi siêu mô hình này thành mô
hình biểu diễn chính sách cụ thể theo các quy tắc ở mục 3.1 của bài báo.
"""
from __future__ import annotations

# 9 lớp UML thông thường (Context là associationclass, khai báo riêng bên dưới)
CLASSES = [
    "Natural_Language_Policy_Statement", "Environment", "Object", "Action",
    "ObjectType", "Subject", "User", "Group", "SubjectType",
]
ASSOCIATION_CLASS = "Context"
NLPS = "Natural_Language_Policy_Statement"

# Thuộc tính theo Fig. 4 (otherAttributes bị loại khi tạo mô hình biểu diễn)
ATTRIBUTES: dict[str, list[tuple[str, str]]] = {
    NLPS: [("idSentence", "String"), ("numberExtractedAttributes", "Integer"),
           ("contextualSentence", "Boolean"), ("otherAttributes", "String")],
    "Environment": [("id", "String"), ("otherAttributes", "String")],
    "Object": [("isNonHumanResource", "Boolean"), ("typeObjectActivated", "String")],
    "ObjectType": [("id", "String"), ("otherAttributes", "String")],
    "Action": [("namesAction", "String"), ("actionsExecuted", "Boolean")],
    "Subject": [("isUser", "Boolean"), ("typeSubjectActivated", "String")],
    "User": [("id", "String"), ("name", "String"), ("roleActivated", "Role"),
             ("typeMembership", "String"), ("position", "String"),
             ("maxRoles", "Integer"), ("otherAttributes", "String")],
    "Group": [("id", "String"), ("name", "String"), ("numberUsers", "Integer"),
              ("maxMembers", "Integer"), ("maxRoles", "Integer"),
              ("hasRolesHierarchy", "Boolean"), ("otherAttributes", "String")],
    "SubjectType": [("id", "String"), ("otherAttributes", "String")],
    "Context": [("id", "String"), ("typeConstraintActivated", "ConstraintType"),
                ("timestamp", "String"), ("timeInPoint", "String"),
                ("duration", "Real"), ("durationUnit", "TimeUnit"),
                ("dayOfWeek", "DayOfWeek"), ("locationORG", "ORG"),
                ("locationFAC", "FAC"), ("locationLOC", "LOC"), ("locationGPE", "GPE"),
                ("network", "Network"), ("distance", "Real"),
                ("distanceUnit", "DistanceUnit"), ("consideredContext", "String"),
                ("otherAttributes", "String")],
}

# (kind, tên, (lớp, bội số, vai trò), (lớp, bội số, vai trò)) — với aggregation,
# đầu thứ nhất là "toàn thể".
ASSOCIATIONS = [
    ("aggregation", "Statement_Subject", (NLPS, "1..*", "statements"), ("Subject", "*", "subjects")),
    ("aggregation", "Statement_Object", (NLPS, "1..*", "statements"), ("Object", "*", "objects")),
    ("aggregation", "Statement_Environment", (NLPS, "1..*", "statements"), ("Environment", "*", "environments")),
    ("aggregation", "Statement_Action", (NLPS, "1..*", "statements"), ("Action", "*", "actions")),
    ("association", "Subject_Action", ("Subject", "*", "subjects"), ("Action", "*", "actions")),
    ("association", "Action_Object", ("Action", "*", "actions"), ("Object", "*", "objects")),
    ("association", "Subject_User", ("Subject", "1", "subject"), ("User", "1", "user")),
    ("association", "Subject_SubjectType", ("Subject", "1", "subject"), ("SubjectType", "1", "subject_type")),
    ("association", "Object_ObjectType", ("Object", "1", "object"), ("ObjectType", "1", "object_type")),
    ("aggregation", "Group_User", ("Group", "*", "groups"), ("User", "*", "users")),
]
CONTEXT_ENDS = (("Action", "*", "actions"), ("Environment", "*", "environments"))

# Giá trị mặc định (placeholder theo Fig. 4); Role/Network/ORG được thay bằng
# giá trị trích xuất ở mô-đun 1.
ENUMS: dict[str, list[str]] = {
    "Role": ["specificRoles"],
    "ConstraintType": ["TemporalConstraint", "SpatialConstraint"],
    "DayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "TimeUnit": ["seconds", "minutes", "hours", "days", "months", "years", "am", "pm"],
    "DistanceUnit": ["meters", "kilometers", "miles"],
    "Device": ["specificDevices"],
    "Network": ["specificNetworks", "specificSystems"],
    "ORG": ["specificCompanies", "specificAgencies", "specificInstitutions",
            "specificUniversities", "specificColleges"],
    "FAC": ["specificBuildings", "specificAirports", "specificHighways", "specificBridges"],
    "LOC": ["specificPhysicalLocations", "specificGeographicalAreas"],
    "GPE": ["specificGeopoliticalEntities"],
}


# Tên vai trò điều hướng Object -> lớp tài nguyên: mặc định là entity_type,
# rút gọn như Fig. 8 / test4 của bài báo (u.subject.actions.objects.agreement).
ROLE_NAME_OVERRIDES = {"visiting_lecturer_agreement": "agreement"}


def role_name(entity_type: str) -> str:
    return ROLE_NAME_OVERRIDES.get(entity_type, entity_type)


def class_name(entity_type: str) -> str:
    """entity_type -> tên lớp tài nguyên phi con người: learning_material -> Learning_Material."""
    return "_".join(part.capitalize() for part in entity_type.split("_") if part) or "Resource"

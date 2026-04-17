"""
Tool submit form đăng ký làm tài xế Xanh SM.
Submissions được lưu vào Dataset/driver_applications.json.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_SUBMISSIONS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "Dataset", "driver_applications.json")
)

VALID_LOCATIONS = [
    "Hà Nội",
    "TP. Hồ Chí Minh",
    "Đà Nẵng",
    "Khánh Hòa",
    "Bà Rịa - Vũng Tàu",
    "Quảng Ninh",
    "Thừa Thiên Huế",
    "Hải Phòng",
    "Vinh",
    "Đồng Nai",
    "Bình Dương",
    "Thái Nguyên",
    "Bắc Ninh",
    "Thanh Hóa",
    "Tây Ninh",
    "Long An",
    "Cần Thơ",
]

DRIVER_APPLICATION_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "submit_driver_application",
        "description": (
            "Lưu đơn đăng ký làm tài xế xe máy điện Xanh SM sau khi đã thu thập đủ thông tin "
            "từ người dùng qua hội thoại. Chỉ gọi tool này khi ĐÃ có đủ: họ tên, SĐT, "
            "hạng bằng lái, địa điểm ứng tuyển."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {
                    "type": "string",
                    "description": "Họ và tên đầy đủ của người đăng ký.",
                },
                "phone": {
                    "type": "string",
                    "description": "Số điện thoại liên hệ.",
                },
                "license_type": {
                    "type": "string",
                    "enum": ["A1", "A2"],
                    "description": "Hạng bằng lái xe máy: 'A1' hoặc 'A2'.",
                },
                "location": {
                    "type": "string",
                    "description": (
                        "Địa điểm ứng tuyển. Một trong: "
                        + ", ".join(f"'{c}'" for c in VALID_LOCATIONS)
                    ),
                },
                "current_need": {
                    "type": "string",
                    "description": "Nhu cầu hiện tại của người đăng ký (không bắt buộc).",
                },
            },
            "required": ["full_name", "phone", "license_type", "location"],
        },
    },
}


def _load_submissions() -> list:
    if not os.path.exists(_SUBMISSIONS_PATH):
        return []
    with open(_SUBMISSIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_submissions(submissions: list) -> None:
    os.makedirs(os.path.dirname(_SUBMISSIONS_PATH), exist_ok=True)
    with open(_SUBMISSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(submissions, f, ensure_ascii=False, indent=2)


def submit_driver_application(
    full_name: str,
    phone: str,
    license_type: str,
    location: str,
    current_need: str = "",
) -> str:
    entry = {
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "full_name": full_name.strip(),
        "phone": phone.strip(),
        "license_type": license_type.upper(),
        "location": location.strip(),
        "current_need": current_need.strip(),
    }

    try:
        submissions = _load_submissions()
        submissions.append(entry)
        _save_submissions(submissions)
        logger.info("[DRIVER_APP] saved entry #%d | %s | %s", len(submissions), full_name, phone)
    except Exception as e:
        logger.error("[DRIVER_APP] failed to save: %s", e)

    return (
        "Cảm ơn bạn đã ĐĂNG KÝ\n"
        "VỊ TRÍ TÀI XẾ XE MÁY ĐIỆN CỦA XANH SM\n"
        "Bác tài có thể liên hệ trực tiếp qua Hotline để được tư vấn chi tiết.\n"
        "096 472 0202"
    )

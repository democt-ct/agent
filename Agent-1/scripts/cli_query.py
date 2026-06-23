import argparse
import base64
import json
import mimetypes
import os
import sys
import uuid
from typing import Any, Dict, List, Optional
from urllib import error, parse, request


def get_json(url: str) -> Any:
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text)
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"请求失败: {exc}") from exc


def post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text)
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"请求失败: {exc}") from exc


def post_multipart(url: str, fields: Dict[str, str], file_field: str, file_path: str) -> Dict[str, Any]:
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    lines: list[bytes] = []

    for key, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        lines.append(f"{value}\r\n".encode("utf-8"))

    file_name = os.path.basename(file_path)
    content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    lines.append(f"--{boundary}\r\n".encode("utf-8"))
    lines.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_name}"\r\n'
        ).encode("utf-8")
    )
    lines.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    lines.append(file_bytes)
    lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(lines)
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text)
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"请求失败: {exc}") from exc


def issue_token(
    base_url: str,
    patient_id: str,
    hospital_id: Optional[str] = None,
    expires_in_minutes: int = 120,
) -> str:
    payload: Dict[str, Any] = {
        "patient_id": patient_id,
        "expires_in_minutes": expires_in_minutes,
    }
    if hospital_id:
        payload["hospital_id"] = hospital_id

    token_resp = post_json(f"{base_url}/api/v1/mcp/auth/issue-token", payload)
    return token_resp["data"]["auth_token"]


def list_patients(base_url: str, hospital_id: str) -> List[Dict[str, Any]]:
    query = parse.urlencode({"hospital_id": hospital_id})
    result = get_json(f"{base_url}/api/v1/patients?{query}")
    if not isinstance(result, list):
        raise RuntimeError("患者列表返回格式错误")
    return result


def resolve_patient_selector(
    base_url: str,
    hospital_id: Optional[str],
    selector: str,
) -> Dict[str, Any]:
    if not hospital_id:
        raise RuntimeError("请先设置 hospital_id，再按编号或序号选择患者。")

    patients = list_patients(base_url, hospital_id)
    if not patients:
        raise RuntimeError("当前院区下没有患者可选。")

    selector = selector.strip()

    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(patients):
            return patients[index - 1]

    for patient in patients:
        if patient.get("id") == selector:
            return patient

    for patient in patients:
        if patient.get("patient_code") == selector:
            return patient

    raise RuntimeError("未找到匹配的患者。/use 支持：患者ID、患者编号，或 /list 结果里的序号。")


def run_query(
    base_url: str,
    question: str,
    patient_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    hospital_id: Optional[str] = None,
    image_path: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "question": question,
        "patient_id": patient_id,
        "auth_token": auth_token,
        "hospital_id": hospital_id,
    }
    payload = {k: v for k, v in payload.items() if v}

    if image_path:
        return post_multipart(
            f"{base_url}/api/v1/mcp/agent/query-with-image",
            payload,
            "image",
            image_path,
        )
    return post_json(f"{base_url}/api/v1/mcp/agent/query", payload)


def synthesize_speech(
    base_url: str,
    text: str,
    voice: Optional[str] = None,
    response_format: str = "mp3",
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "text": text,
        "response_format": response_format,
    }
    if voice:
        payload["voice"] = voice
    return post_json(f"{base_url}/api/v1/mcp/agent/speech", payload)


def save_audio_response(speech_response: Dict[str, Any], output_path: Optional[str] = None) -> str:
    response_format = speech_response.get("response_format", "mp3")
    if not output_path:
        output_path = f"tts_answer_{uuid.uuid4().hex[:8]}.{response_format}"

    audio_bytes = base64.b64decode(speech_response["audio_base64"])
    with open(output_path, "wb") as f:
        f.write(audio_bytes)
    return os.path.abspath(output_path)


def print_summary(tool_name: str, data: Dict[str, Any]) -> None:
    patient = data.get("patient") or {}
    if patient:
        print(
            f"- 患者: {patient.get('full_name', '-')} | 编号: {patient.get('patient_code', '-')} | 院区: {patient.get('hospital_id', '-')}"
        )

    if tool_name == "image_analysis_only":
        print("- 查询模式: 仅基于图片回答")
        if data.get("image_analysis"):
            print(f"- 图片摘要: {data.get('image_analysis')}")
        return

    if tool_name == "verify_identity":
        print(f"- 认证状态: {'成功' if data.get('authenticated') else '失败'}")
        print(f"- token 过期时间: {data.get('expires_at', '-')}")
        return

    if tool_name == "get_visit_records":
        records = data.get("visit_records") or []
        print(f"- 命中就诊记录: {data.get('count', len(records))} 条")
        if records:
            latest = records[0]
            print(f"- 最近一次就诊: {latest.get('visit_date', '-')} | {latest.get('department', '-')} | {latest.get('doctor_name', '-')} | {latest.get('visit_summary', '-')}")
        return

    if tool_name == "get_medical_records":
        records = data.get("medical_records") or []
        print(f"- 命中病历: {data.get('count', len(records))} 条")
        if records:
            latest = records[0]
            print(f"- 最近一条病历: {latest.get('record_date', '-')} | {latest.get('title', '-')} | {latest.get('diagnosis', '-')}")
        return

    if tool_name == "get_patient_profile":
        medical_records = data.get("medical_records") or []
        visit_records = data.get("visit_records") or []
        print(f"- 病历数量: {len(medical_records)}")
        print(f"- 就诊记录数量: {len(visit_records)}")
        if medical_records:
            latest_medical = medical_records[0]
            print(f"- 最近病历: {latest_medical.get('record_date', '-')} | {latest_medical.get('title', '-')} | {latest_medical.get('diagnosis', '-')}")
        if visit_records:
            latest_visit = visit_records[0]
            print(f"- 最近就诊: {latest_visit.get('visit_date', '-')} | {latest_visit.get('department', '-')} | {latest_visit.get('doctor_name', '-')} | {latest_visit.get('visit_summary', '-')}")
        return

    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_result(result: Dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    tool_name = result.get("chosen_tool", "")
    tool_result = result.get("tool_result", {}) if isinstance(result, dict) else {}
    data = tool_result.get("data", {}) if isinstance(tool_result, dict) else {}

    print("问题:", result.get("question", ""))
    print("选中的工具:", tool_name)
    if result.get("image_analysis"):
        print("图片摘要:")
        print(result.get("image_analysis", ""))
    print("最终回答:")
    print(result.get("answer", ""))
    if result.get("speech_text"):
        print("\n播报稿:")
        print(result.get("speech_text", ""))
    print("\n查询摘要:")
    print_summary(tool_name, data)
    print("\n提示: 如需查看完整 JSON，请在命令后加 --json")


def print_patients(patients: List[Dict[str, Any]]) -> None:
    if not patients:
        print("当前院区下没有患者。")
        return

    print(f"共找到 {len(patients)} 位患者：")
    for idx, patient in enumerate(patients, start=1):
        print(
            f"{idx}. id={patient.get('id')} | 姓名={patient.get('full_name')} | 编号={patient.get('patient_code')} | 院区={patient.get('hospital_id')}"
        )


def run_interactive(
    base_url: str,
    patient_id: Optional[str],
    hospital_id: Optional[str],
    auth_token: Optional[str],
    expires_in_minutes: int,
    voice: Optional[str],
    response_format: str,
) -> int:
    current_patient_id = patient_id
    current_hospital_id = hospital_id
    current_auth_token = auth_token
    last_answer = ""

    print("进入交互模式。输入问题即可查询，输入 /help 查看命令。")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出交互模式。")
            return 0

        if not raw:
            continue

        if raw in {"/exit", "/quit"}:
            print("已退出交互模式。")
            return 0

        if raw == "/help":
            print("可用命令：")
            print("/list <hospital_id>      查看指定院区下的患者列表")
            print("/use <selector>         切换当前患者，支持序号 / 患者编号 / 患者ID")
            print("/hospital <hospital_id> 设置当前默认院区")
            print("/token                  为当前患者重新签发 token")
            print("/speak [output_path]    把上一条回答导出为语音文件")
            print("/whoami                 查看当前患者上下文")
            print("/clear                  清空当前患者和 token")
            print("/exit                   退出")
            print("交互模式暂不支持图片上传，图片问答请用 --image 单次命令。")
            continue

        if raw.startswith("/list"):
            parts = raw.split(maxsplit=1)
            target_hospital_id = parts[1] if len(parts) > 1 else current_hospital_id
            if not target_hospital_id:
                print("请先提供 hospital_id，例如 /list hospital-a")
                continue
            try:
                patients = list_patients(base_url, target_hospital_id)
                current_hospital_id = target_hospital_id
                print_patients(patients)
            except Exception as exc:
                print(f"查询患者列表失败: {exc}")
            continue

        if raw.startswith("/use"):
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                print("请提供患者选择器，例如 /use 1、/use P0001 或 /use b10e5b17-xxxx")
                continue
            selector = parts[1].strip()
            try:
                patient = resolve_patient_selector(base_url, current_hospital_id, selector)
                current_patient_id = patient["id"]
                current_hospital_id = patient.get("hospital_id", current_hospital_id)
                current_auth_token = None
                print(
                    f"已切换当前患者: {patient.get('full_name')} | 编号={patient.get('patient_code')} | id={current_patient_id}"
                )
            except Exception as exc:
                print(f"切换患者失败: {exc}")
            continue

        if raw.startswith("/hospital"):
            parts = raw.split(maxsplit=1)
            if len(parts) < 2:
                print("请提供 hospital_id，例如 /hospital hospital-a")
                continue
            current_hospital_id = parts[1].strip()
            print(f"已设置当前院区: {current_hospital_id}")
            continue

        if raw == "/token":
            if not current_patient_id:
                print("当前还没有选中患者，请先用 /use 切换患者。")
                continue
            try:
                current_auth_token = issue_token(
                    base_url=base_url,
                    patient_id=current_patient_id,
                    hospital_id=current_hospital_id,
                    expires_in_minutes=expires_in_minutes,
                )
                print("已为当前患者签发新的 auth_token。")
            except Exception as exc:
                print(f"签发 token 失败: {exc}")
            continue

        if raw.startswith("/speak"):
            if not last_answer.strip():
                print("当前还没有上一条可播报的回答。")
                continue
            parts = raw.split(maxsplit=1)
            output_path = parts[1].strip() if len(parts) > 1 else None
            try:
                speech_response = synthesize_speech(
                    base_url=base_url,
                    text=last_answer,
                    voice=voice,
                    response_format=response_format,
                )
                saved_path = save_audio_response(speech_response, output_path)
                print(f"语音已导出: {saved_path}")
            except Exception as exc:
                print(f"语音导出失败: {exc}")
            continue

        if raw == "/whoami":
            print("当前上下文：")
            print(f"- patient_id: {current_patient_id or '未设置'}")
            print(f"- hospital_id: {current_hospital_id or '未设置'}")
            print(f"- auth_token: {'已设置' if current_auth_token else '未设置'}")
            continue

        if raw == "/clear":
            current_patient_id = None
            current_hospital_id = None
            current_auth_token = None
            last_answer = ""
            print("已清空当前上下文。")
            continue

        if not current_patient_id and not current_auth_token:
            print("当前没有患者上下文。请先使用 /list 查看患者，再用 /use 选择患者。")
            continue

        try:
            if not current_auth_token and current_patient_id:
                current_auth_token = issue_token(
                    base_url=base_url,
                    patient_id=current_patient_id,
                    hospital_id=current_hospital_id,
                    expires_in_minutes=expires_in_minutes,
                )
                print("已自动为当前患者签发 auth_token。")

            result = run_query(
                base_url=base_url,
                question=raw,
                patient_id=current_patient_id,
                auth_token=current_auth_token,
                hospital_id=current_hospital_id,
            )
            last_answer = result.get("speech_text") or result.get("answer", "")
            print_result(result)
        except Exception as exc:
            print(f"查询失败: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="终端中直接调用 MCP Agent 查询患者信息")
    parser.add_argument("question", nargs="?", help="要提问的中文问题")
    parser.add_argument("--patient-id", dest="patient_id", help="患者 ID")
    parser.add_argument("--auth-token", dest="auth_token", help="认证 token")
    parser.add_argument("--hospital-id", dest="hospital_id", help="院区 ID")
    parser.add_argument("--image", dest="image_path", help="图片路径，启用多模态问答")
    parser.add_argument(
        "--auto-token",
        action="store_true",
        help="如果未提供 auth_token，则基于 patient_id 自动签发 token 后再查询",
    )
    parser.add_argument(
        "--expires-in-minutes",
        dest="expires_in_minutes",
        type=int,
        default=120,
        help="自动签发 token 时的有效分钟数，默认 120",
    )
    parser.add_argument(
        "--list-patients",
        action="store_true",
        help="查询当前 hospital_id 下的患者列表",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="进入交互模式，可切换患者并持续提问",
    )
    parser.add_argument(
        "--speak",
        action="store_true",
        help="在查询完成后，把 answer 再导出为语音文件",
    )
    parser.add_argument(
        "--audio-output",
        help="导出的语音文件路径，默认自动生成",
    )
    parser.add_argument(
        "--voice",
        help="语音音色名称，可选；具体取决于后端配置的 TTS 模型",
    )
    parser.add_argument(
        "--audio-format",
        default="mp3",
        help="语音输出格式，默认 mp3",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="服务地址，默认 http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出完整 JSON，而不是简洁模式",
    )
    args = parser.parse_args()

    if args.interactive:
        return run_interactive(
            base_url=args.base_url,
            patient_id=args.patient_id,
            hospital_id=args.hospital_id,
            auth_token=args.auth_token,
            expires_in_minutes=args.expires_in_minutes,
            voice=args.voice,
            response_format=args.audio_format,
        )

    if args.list_patients:
        if not args.hospital_id:
            raise RuntimeError("使用 --list-patients 时请同时提供 --hospital-id。")
        patients = list_patients(args.base_url, args.hospital_id)
        print_patients(patients)
        return 0

    if not args.question:
        raise RuntimeError("请提供问题，或使用 --interactive / --list-patients。")

    if args.image_path and not os.path.exists(args.image_path):
        raise RuntimeError(f"图片不存在: {args.image_path}")

    if not args.auth_token and not args.patient_id and not args.image_path:
        raise RuntimeError("请至少提供 --patient-id、--auth-token 或 --image 其中之一。")

    auth_token = args.auth_token
    if not auth_token and args.auto_token and args.patient_id:
        auth_token = issue_token(
            base_url=args.base_url,
            patient_id=args.patient_id,
            hospital_id=args.hospital_id,
            expires_in_minutes=args.expires_in_minutes,
        )
        print("已自动签发 auth_token")

    result = run_query(
        base_url=args.base_url,
        question=args.question,
        patient_id=args.patient_id,
        auth_token=auth_token,
        hospital_id=args.hospital_id,
        image_path=args.image_path,
    )
    print_result(result, as_json=args.json)

    if args.speak:
        speech_response = synthesize_speech(
            base_url=args.base_url,
            text=result.get("speech_text") or result.get("answer", ""),
            voice=args.voice,
            response_format=args.audio_format,
        )
        saved_path = save_audio_response(speech_response, args.audio_output)
        print(f"语音已导出: {saved_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())



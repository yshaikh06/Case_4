from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line
import hashlib
from uuid import uuid4

app = Flask(__name__)
# Allow cross-origin requests so the static HTML can POST from localhost or file://
CORS(app, resources={r"/v1/*": {"origins": "*"}})
def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "API is alive",
        "utc_time": datetime.now(timezone.utc).isoformat()
    })

@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid_json", "detail": "Body must be application/json"}), 400
    if "user_agent" not in payload or payload["user_agent"] is None:
        payload["user_agent"] = request.headers.get("User-Agent")
    if "email" in payload and payload["email"] is not None:
        payload["email"] = hash_value(payload["email"])
    if "age" in payload and payload["age"] is not None:
        payload["age"] = hash_value(str(payload["age"]))
    if "submission_id" not in payload or not payload["submission_id"]:
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        email_hash = payload.get("email", str(uuid4()))
        payload["submission_id"] = hashlib.sha256((payload["email"] + now_str).encode()).hexdigest()
    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    record = StoredSurveyRecord(
        **submission.dict(),
        received_at=datetime.now(timezone.utc),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr or "")
    )
    append_json_line(record.dict())
    return jsonify({"status": "ok"}), 201

if __name__ == "__main__":
    app.run(port=5000, debug=True)

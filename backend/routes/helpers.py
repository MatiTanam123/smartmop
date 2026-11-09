from flask import jsonify, request

def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({
            "success": False,
            "message": "Body harus berupa JSON object"
        }), 400)
    return data, None

def error_response(message, status=400):
    return jsonify({"success": False, "message": message}), status

def success_response(data=None, message="Berhasil", status=200):
    result = {"success": True, "message": message}
    if data is not None:
        result["data"] = data
    return jsonify(result), status

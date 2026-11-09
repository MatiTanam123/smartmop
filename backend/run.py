from app import create_app

app = create_app()

if __name__ == "__main__":
    # Untuk development lokal saja. Saat deploy gunakan server WSGI seperti Gunicorn.
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])

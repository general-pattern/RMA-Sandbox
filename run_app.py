import threading
import webview  # pip install pywebview
from app import app  # your existing Flask app object

def start_flask():
    # debug=False so it doesn't try to reload itself
    app.run(host="127.0.0.1", port=5000, debug=False)

if __name__ == "__main__":
    # Start Flask in the background
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    # Open it in a desktop window
    webview.create_window(
        "RMA System",
        "http://127.0.0.1:5000",
        width=1200,
        height=800,
    )
    webview.start()

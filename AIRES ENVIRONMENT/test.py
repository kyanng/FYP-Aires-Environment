import os
import hmac
import hashlib, base64, json, random, string
from datetime import datetime, timedelta
from flask import Flask, request, render_template
from dotenv import load_dotenv
import urllib.request, urllib.error

load_dotenv()

app = Flask(__name__)

QR_STORE = {}

URL = os.getenv("NETS_URL")
KEY_ID = os.getenv("NETS_KEY_ID")
SECRET_KEY = os.getenv("NETS_SECRET_KEY")
HOST_TID = os.getenv("NETS_HOST_TID")
HOST_MID = os.getenv("NETS_HOST_MID")

ECOQPAY_URL = os.getenv("ECOQPAY_URL")
ECOQPAY_API_KEY = os.getenv("ECOQPAY_API_KEY")

INVOICE_SECRET = os.getenv("INVOICE_SECRET", "change-this-to-a-long-random-secret")

APP_BASE_URL = "http://127.0.0.1:9999"


def generate_ecoqpay_encryption_key():
    return ''.join(
        random.choices("123456789", k=1) +
        random.choices("0123456789", k=11)
    )


def generate_ecoqpay_qr(link1, link2="", link3=""):
    encryption_key = generate_ecoqpay_encryption_key()

    payload = {
        "link1": link1,
        "link2": link2,
        "link3": link3,
        "encryption-key": encryption_key
    }

    body = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "API-KEY": ECOQPAY_API_KEY
    }

    req = urllib.request.Request(
        ECOQPAY_URL,
        data=body,
        headers=headers,
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def format_amount(amount_input):
    if not amount_input:
        amount_input = "100"

    amount = float(amount_input)
    cents = int(round(amount * 100))

    return str(cents).zfill(12), f"{amount:.2f}"


def sign_invoice(qr_id, stan, amount, invoice_ref, retrieval_ref):
    message = f"{qr_id}:{stan}:{amount}:{invoice_ref}:{retrieval_ref}"

    return hmac.new(
        INVOICE_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


@app.route("/qr/<qr_id>")
def qr_page(qr_id):
    qr_data = QR_STORE.get(qr_id)

    if not qr_data:
        return "QR expired or not found", 404

    if datetime.now() > qr_data["expires_at"]:
        del QR_STORE[qr_id]
        return "QR expired", 410

    qr_code = qr_data["qr_code"]
    expires_at = qr_data["expires_at"].timestamp()

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>NETS QR</title>

        <style>
            body {{
                font-family: Arial;
                background: #f5f5f5;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }}

            .card {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                text-align: center;
            }}

            img {{
                max-width: 320px;
            }}

            .countdown {{
                font-size: 18px;
                font-weight: bold;
                color: #e8001d;
                margin-bottom: 20px;
            }}
        </style>
    </head>

    <body>
        <div class="card">
            <h2>NETS QR Payment</h2>

            <p class="countdown">
                Expires in <span id="timer">60</span>s
            </p>

            <img id="qrImage" src="data:image/png;base64,{qr_code}">
        </div>

        <script>
            const expiresAt = {expires_at} * 1000;

            function updateCountdown() {{
                const now = Date.now();
                const remaining = Math.max(
                    0,
                    Math.floor((expiresAt - now) / 1000)
                );

                document.getElementById("timer").textContent = remaining;

                if (remaining <= 0) {{
                    document.querySelector(".card").innerHTML = `
                        <h2>QR Expired</h2>
                        <p>This QR code has expired. Please generate a new one.</p>
                    `;
                    clearInterval(timerInterval);
                }}
            }}

            updateCountdown();
            const timerInterval = setInterval(updateCountdown, 1000);
        </script>
    </body>
    </html>
    """


@app.route("/invoice/<qr_id>")
def invoice_page(qr_id):
    sig = request.args.get("sig", "")
    data = QR_STORE.get(qr_id)

    if not data:
        return "Invoice not found or expired", 404

    expected_sig = sign_invoice(
        qr_id,
        data["stan"],
        data["amount"],
        data["invoice_ref"],
        data["retrieval_ref"]
    )

    if not hmac.compare_digest(sig, expected_sig):
        return "Invalid invoice signature", 403

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verified Invoice</title>
        <style>
            body {{
                font-family: Arial;
                background: #f5f5f5;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }}

            .card {{
                background: white;
                padding: 35px;
                border-radius: 18px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                max-width: 540px;
                width: 100%;
            }}

            .verified {{
                color: #198754;
                font-weight: bold;
                margin-bottom: 20px;
            }}

            .row {{
                display: flex;
                justify-content: space-between;
                border-bottom: 1px solid #eee;
                padding: 12px 0;
                gap: 20px;
            }}

            .label {{
                color: #666;
            }}

            .value {{
                font-weight: bold;
                text-align: right;
                word-break: break-all;
            }}

            .note {{
                margin-top: 20px;
                font-size: 13px;
                color: #666;
            }}
        </style>
    </head>

    <body>
        <div class="card">
            <h2>Invoice Verification</h2>
            <p class="verified">Verified: Signature Valid</p>

            <div class="row">
                <span class="label">Amount</span>
                <span class="value">SGD {data["amount"]}</span>
            </div>

            <div class="row">
                <span class="label">STAN</span>
                <span class="value">{data["stan"]}</span>
            </div>

            <div class="row">
                <span class="label">Invoice Ref</span>
                <span class="value">{data["invoice_ref"]}</span>
            </div>

            <div class="row">
                <span class="label">Retrieval Ref</span>
                <span class="value">{data["retrieval_ref"]}</span>
            </div>

            <div class="row">
                <span class="label">Generated At</span>
                <span class="value">{data["created_at"]}</span>
            </div>

            <div class="row">
                <span class="label">Expires At</span>
                <span class="value">{data["expires_at"]}</span>
            </div>

            <p class="note">
                This invoice was generated by the authorised server and verified using a server-side HMAC signature.
            </p>
        </div>
    </body>
    </html>
    """


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    try:
        amount_raw = request.form.get("amount", "").strip()
        stan_raw = request.form.get("stan", "").strip()

        AMOUNT, display_amount = format_amount(amount_raw)

        stan = stan_raw if stan_raw else str(random.randint(1, 999999)).zfill(6)

        if not stan.isdigit() or len(stan) != 6:
            raise ValueError("STAN must be exactly 6 digits.")

        now = datetime.now()

        transaction_time = now.strftime("%H%M%S")
        transaction_date = now.strftime("%m%d")

        retrieval_ref = now.strftime("%y%m%d") + stan
        invoice_ref = now.strftime("%Y%m%d") + stan

        payload = {
            "mti": "0200",
            "process_code": "990000",
            "amount": AMOUNT,
            "stan": stan,
            "transaction_time": transaction_time,
            "transaction_date": transaction_date,
            "entry_mode": "000",
            "condition_code": "85",
            "institution_code": "20000000001",
            "retrieval_ref": retrieval_ref,
            "host_tid": HOST_TID,
            "host_mid": HOST_MID,
            "getQRCode": "Y",
            "communication_data": [
                {
                    "type": "https_proxy",
                    "category": "URL",
                    "destination": "https://netspay.uat.net:8801/secapi/notify/dynamic",
                    "addon": {
                        "external_API_keyID": KEY_ID
                    }
                }
            ],
            "npx_data": {
                "E103": HOST_TID,
                "E201": AMOUNT,
                "E202": "SGD"
            },
            "invoice_ref": invoice_ref
        }

        body = json.dumps(payload, separators=(",", ":"))

        sign = base64.b64encode(
            hashlib.sha256((body + SECRET_KEY).encode("utf-8")).digest()
        ).decode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "KeyId": KEY_ID,
            "Sign": sign
        }

        req = urllib.request.Request(
            URL,
            data=body.encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                response_text = response.read().decode("utf-8")

        except urllib.error.HTTPError as e:
            response_text = e.read().decode("utf-8")

        result = json.loads(response_text)

        if result.get("response_code") == "00" and result.get("qr_code"):
            random_suffix = ''.join(
                random.choices(
                    string.ascii_letters + string.digits,
                    k=6
                )
            )

            qr_id = stan + random_suffix

            generated_at = datetime.now()
            expires_at = generated_at + timedelta(minutes=1)

            invoice_sig = sign_invoice(
                qr_id,
                stan,
                display_amount,
                invoice_ref,
                retrieval_ref
            )

            QR_STORE[qr_id] = {
                "qr_code": result["qr_code"],
                "created_at": generated_at,
                "expires_at": expires_at,
                "amount": display_amount,
                "stan": stan,
                "invoice_ref": invoice_ref,
                "retrieval_ref": retrieval_ref,
                "signature": invoice_sig
            }

            qr_url = f"{APP_BASE_URL}/qr/{qr_id}"
            invoice_url = f"{APP_BASE_URL}/invoice/{qr_id}?sig={invoice_sig}"

            ecoqpay_png_bytes = generate_ecoqpay_qr(
                link1=qr_url,
                link2=invoice_url,
                link3=""
            )

            ecoqpay_qr_base64 = base64.b64encode(ecoqpay_png_bytes).decode("utf-8")

            print("Temp NETS QR URL:", qr_url)
            print("Invoice URL:", invoice_url)

            return render_template(
                "index.html",
                qr=ecoqpay_qr_base64,
                qr_url=qr_url,
                stan=stan,
                display_amount=display_amount,
                txn_identifier=result.get("txn_identifier")
            )

        return render_template(
            "index.html",
            error=json.dumps(result, indent=2)
        )

    except Exception as e:
        return render_template(
            "index.html",
            error=str(e)
        )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=9999)
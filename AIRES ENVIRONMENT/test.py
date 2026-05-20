import hashlib, base64, json, random
from datetime import datetime
from flask import Flask, request, render_template
import urllib.request, urllib.error

app = Flask(__name__)

URL = "https://uat-api.nets.com.sg/uat/merchantservices/qr/dynamic/v1/order/request"

KEY_ID = "231e4c11-135a-4457-bc84-3cc6d3565506"
SECRET_KEY = "16c573bf-0721-478a-8635-38e53e3badf1"

HOST_TID = "37066801"
HOST_MID = "11137066800"


def format_amount(amount_input):
    if not amount_input:
        amount_input = "100"

    amount = float(amount_input)
    cents = int(round(amount * 100))

    return str(cents).zfill(12), f"{amount:.2f}"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template('index.html')

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
            return render_template(
                'index.html',
                qr=result["qr_code"],
                stan=stan,
                display_amount=display_amount,
                txn_identifier=result.get("txn_identifier")
            )

        return render_template(
            'index.html',
            error=json.dumps(result, indent=2)
        )

    except Exception as e:
        return render_template('index.html', error=str(e))

if __name__ == "__main__":
        app.run(debug=True, host="127.0.0.1", port=9999)

#hii
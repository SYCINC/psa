
from flask import Flask, request, render_template_string, redirect
import requests
from bs4 import BeautifulSoup
import os
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<title>PSA Cert Lookup</title>
<h2>Single Cert Lookup</h2>
<form method="POST">
  Enter PSA Cert #: <input type="text" name="cert" required>
  <input type="submit" value="Lookup">
</form>

<h2>Batch Upload</h2>
<form method="POST" action="/batch-upload" enctype="multipart/form-data">
  Upload CSV (column: cert_number): <input type="file" name="file" accept=".csv" required>
  <input type="submit" value="Upload">
</form>

{% if result %}
  <h3>Result for Cert #{{ cert }}</h3>
  <ul>
    <li><strong>Card Name:</strong> {{ result.card_name }}</li>
    <li><strong>Grade:</strong> {{ result.grade }}</li>
    <li><strong>Set:</strong> {{ result.set }}</li>
    <li><strong>Card Number:</strong> {{ result.card_number }}</li>
    <li><strong>Population:</strong> {{ result.population }}</li>
    <li><strong>Image:</strong> <br><img src="{{ result.image_link }}" width="300"></li>
  </ul>
{% endif %}
"""

def push_to_google_sheet(cert, result):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("PSA Lookups").sheet1
    sheet.append_row([
        cert,
        result["card_name"],
        result["grade"],
        result["set"],
        result["card_number"],
        result["population"],
        result["image_link"]
    ])

def lookup_cert(cert):
    url = f"https://www.psacard.com/cert/{cert}"
    try:
        response = requests.get(url, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')

        card_name = soup.find("div", class_="cert-details-title").get_text(strip=True)
        grade = soup.find("div", class_="cert-grade").get_text(strip=True)
        set_info = soup.find("div", class_="cert-details-subtitle").get_text(strip=True)

        pop_count = ""
        card_number = ""
        for detail in soup.find_all("div", class_="cert-data-item"):
            label = detail.find("div", class_="cert-data-label").get_text(strip=True)
            value = detail.find("div", class_="cert-data-value").get_text(strip=True)
            if "Population" in label:
                pop_count = value
            elif "Card Number" in label:
                card_number = value

        image_tag = soup.find("img", class_="cert-image")
        image_link = image_tag['src'] if image_tag else ""

        result = {
            "card_name": card_name,
            "grade": grade,
            "set": set_info,
            "card_number": card_number,
            "population": pop_count,
            "image_link": image_link
        }

    except Exception as e:
        result = {
            "card_name": "Error fetching data",
            "grade": str(e),
            "set": "-",
            "card_number": "-",
            "population": "-",
            "image_link": ""
        }

    return result

@app.route('/', methods=['GET', 'POST'])
def lookup():
    result = None
    cert = None
    if request.method == 'POST':
        cert = request.form['cert'].strip()
        result = lookup_cert(cert)
        push_to_google_sheet(cert, result)
    return render_template_string(HTML_TEMPLATE, result=result, cert=cert)

@app.route('/batch-upload', methods=['POST'])
def batch_upload():
    file = request.files['file']
    if file:
        df = pd.read_csv(file)
        for cert in df['cert_number']:
            cert = str(cert).strip()
            result = lookup_cert(cert)
            push_to_google_sheet(cert, result)
    return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

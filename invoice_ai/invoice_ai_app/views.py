# import os
# import tempfile
# import json
# import pandas as pd
# import openai
# from pdf2image import convert_from_path
# from PIL import Image
# import pytesseract
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.views.decorators.http import require_POST
# from django.conf import settings
# import zipfile
# import shutil

# # ================================
# # Configuration
# # ================================

# openai.api_key = "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"
#   # <-- Replace with your key

# MEDIA_DIR = os.path.join(settings.BASE_DIR, "media")
# os.makedirs(MEDIA_DIR, exist_ok=True)

# # ================================
# # Helper Functions
# # ================================

# def extract_text_from_pdf_ocr(pdf_path: str) -> str:
#     """
#     Extract text from a scanned PDF using OCR (pytesseract + pdf2image).
#     """
#     text = ""
#     try:
#         images = convert_from_path(pdf_path)
#         for i, img in enumerate(images):
#             page_text = pytesseract.image_to_string(img)
#             text += f"\n--- Page {i+1} ---\n{page_text}"
#         return text.strip()
#     except Exception as e:
#         raise RuntimeError(f"OCR failed: {e}")


# def extract_invoice_data(invoice_text: str) -> dict:
#     """
#     Extract structured invoice data from OCR text using OpenAI GPT.
#     """
#     prompt = f"""
# You are a Tally accounting expert and an invoice data analyst. Your task is to carefully extract invoice data from text and return it in strict JSON format that can be directly updated into an Excel sheet. 

# The invoices may use different names for fields (for example, "Invoice No" might appear as "Bill No", "Invoice Number", or "Inv No"). 
# Your job is to identify these variations and map them to the correct standardized fields.

# Standard fields to extract:
# - Sl.no
# - Month
# - Invoice Date
# - Invoice Name
# - Invoice No
# - GST
# - Vendor Name
# - Total Amount
# - Payment status
# - Audit Status
# - Remarks
# - Supporting Docs

# Invoice text:
# {invoice_text}

# Instructions:
# 1. Map any variations of field names in the invoice text to the standard fields above.
# 2. Fill in the values correctly, maintaining proper formatting (e.g., date formats, currency).
# 3. If the invoice lists individual line items and no total is provided, **calculate the total amount by summing the line items** and use that as the Total Amount.
# 4. If a field is missing and cannot be inferred, set its value as an empty string.
# 5. Return **only valid JSON** with the standard field names as keys.

# Example output format:
# {{
#   "Sl.no": "1",
#   "Month": "October",
#   "Invoice Date": "25-Oct-25",
#   "Invoice Name": "Sales Invoice",
#   "Invoice No": "INV-2024-1004",
#   "GST": "GSTIN 07AAECR2971C1Z3",
#   "Vendor Name": "Americon consulting group USA",
#   "Total Amount": "456732.21(USD)",
#   "Payment status": "",
#   "Audit Status": "",
#   "Remarks": "",
#   "Supporting Docs": ""
# }}
# """

#     try:
#         response = openai.ChatCompletion.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You are an expert invoice parser. Respond in pure JSON format only."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0,
#             max_tokens=1200
#         )
#         result_text = response["choices"][0]["message"]["content"]

#         # Ensure valid JSON
#         try:
#             data = json.loads(result_text)
#         except json.JSONDecodeError:
#             import re
#             json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
#             data = json.loads(json_match.group(0)) if json_match else {"raw_text": result_text}

#         return data

#     except Exception as e:
#         raise RuntimeError(f"OpenAI extraction failed: {e}")


# def update_excel(excel_path: str, extracted_data: dict) -> str:
#     """
#     Append extracted invoice data to an existing Excel file.
#     If the file doesn't exist, create a new one with proper columns.
#     Auto-increments 'Sl.no' if not provided.
#     Returns path to the updated Excel file.
    
#     expected keys in extracted_data:
#     ['Sl.no', 'Month', 'Invoice Date', 'Invoice Name', 'Invoice No', 
#      'GST', 'Vendor Name', 'Total Amount', 'Payment status', 
#      'Audit Status', 'Remarks', 'Supporting Docs']
#     """
#     try:
#         # Load existing Excel or create new with proper columns
#         columns = ['Sl.no', 'Month', 'Invoice Date', 'Invoice Name', 'Invoice No',
#                    'GST', 'Vendor Name', 'Total Amount', 'Payment status',
#                    'Audit Status', 'Remarks', 'Supporting Docs']
        
#         if os.path.exists(excel_path):
#             df = pd.read_excel(excel_path)
#         else:
#             df = pd.DataFrame(columns=columns)

#         # Auto-increment Sl.no if missing or empty
#         if 'Sl.no' not in extracted_data or extracted_data['Sl.no'] == "":
#             extracted_data['Sl.no'] = len(df) + 1

#         # Ensure extracted_data has all columns
#         for col in columns:
#             if col not in extracted_data:
#                 extracted_data[col] = ""  # Fill missing fields with empty string

#         # Append new row
#         new_row = pd.DataFrame([extracted_data])
#         updated_df = pd.concat([df, new_row], ignore_index=True)

#         # Save back to Excel
#         updated_df.to_excel(excel_path, index=False)
#         return excel_path

#     except Exception as e:
#         raise RuntimeError(f"Excel update failed: {e}")

# # ================================
# # Django View
# # ================================

# @csrf_exempt
# @require_POST
# def upload_invoice(request):
#     """
#     API endpoint: upload ZIP of invoice PDFs (as 'invoice') + Excel, extract data from each, update Excel.
#     """
#     invoice_zip = request.FILES.get("invoice")
#     excel_file = request.FILES.get("excel")

#     if not invoice_zip or not excel_file:
#         return JsonResponse({"error": "Both 'invoice' (ZIP) and 'excel' files are required."}, status=400)

#     zip_path = None
#     excel_path = None
#     extract_dir = None
#     all_extracted = []

#     try:
#         # Save files temporarily
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as zip_tmp:
#             for chunk in invoice_zip.chunks():
#                 zip_tmp.write(chunk)
#             zip_path = zip_tmp.name

#         with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as xl_tmp:
#             for chunk in excel_file.chunks():
#                 xl_tmp.write(chunk)
#             excel_path = xl_tmp.name

#         # Extract ZIP to temp dir
#         extract_dir = tempfile.mkdtemp()
#         with zipfile.ZipFile(zip_path, 'r') as zip_ref:
#             zip_ref.extractall(extract_dir)

#         # Find PDF files recursively
#         pdf_paths = []
#         for root, dirs, files in os.walk(extract_dir):
#             for file in files:
#                 if file.lower().endswith('.pdf'):
#                     pdf_paths.append(os.path.join(root, file))

#         if not pdf_paths:
#             return JsonResponse({"error": "No PDF files found in the ZIP archive."}, status=400)

#         # Process each PDF
#         for pdf_path in pdf_paths:
#             # 1️⃣ OCR extraction
#             invoice_text = extract_text_from_pdf_ocr(pdf_path)

#             # 2️⃣ GPT extraction
#             extracted_data = extract_invoice_data(invoice_text)
#             all_extracted.append(extracted_data)

#             # 3️⃣ Update Excel
#             update_excel(excel_path, extracted_data)

#         # Move updated Excel to media dir
#         media_excel_path = os.path.join(MEDIA_DIR, os.path.basename(excel_path))
#         shutil.move(excel_path, media_excel_path)
#         file_url = request.build_absolute_uri(f"/media/{os.path.basename(media_excel_path)}")

#         return JsonResponse({
#             "message": f"✅ Processed {len(pdf_paths)} invoices successfully.",
#             "extracted_data": all_extracted,
#             "updated_excel_path": file_url
#         })

#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=500)

#     finally:
#         # Cleanup temp files
#         if zip_path and os.path.exists(zip_path):
#             os.remove(zip_path)
#         if extract_dir:
#             shutil.rmtree(extract_dir, ignore_errors=True)
#         if excel_path and os.path.exists(excel_path):
#             os.remove(excel_path)


import os
import tempfile
import json
import pandas as pd
import openai
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

# ================================
# Configuration
# ================================
openai.api_key = "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"

  # <-- Replace with your key

MEDIA_DIR = os.path.join(settings.BASE_DIR, "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

# ================================
# Helper Functions
# ================================

def extract_text_from_pdf_ocr(pdf_path: str) -> str:
    """
    Extract text from a scanned PDF using OCR (pytesseract + pdf2image).
    """
    text = ""
    try:
        images = convert_from_path(pdf_path)
        for i, img in enumerate(images):
            page_text = pytesseract.image_to_string(img)
            text += f"\n--- Page {i+1} ---\n{page_text}"
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"OCR failed: {e}")


def extract_invoice_data(invoice_text: str) -> dict:
    """
    Extract structured invoice data from OCR text using OpenAI GPT.
    """
    prompt = f"""
You are a Tally accounting expert and an invoice data analyst. Your task is to carefully extract invoice data from text and return it in strict JSON format that can be directly updated into an Excel sheet. 

The invoices may use different names for fields (for example, "Invoice No" might appear as "Bill No", "Invoice Number", or "Inv No"). 
Your job is to identify these variations and map them to the correct standardized fields.

Standard fields to extract:
- Sl.no
- Month
- Invoice Date
- Invoice Name
- Invoice No
- GST
- Vendor Name
- Total Amount
- Payment status
- Audit Status
- Remarks
- Supporting Docs

Invoice text:
{invoice_text}

Instructions:
1. Map any variations of field names in the invoice text to the standard fields above.
2. Fill in the values correctly, maintaining proper formatting (e.g., date formats, currency).
3. If the invoice lists individual line items and no total is provided, **calculate the total amount by summing the line items** and use that as the Total Amount.
4. If a field is missing and cannot be inferred, set its value as an empty string.
5. Return **only valid JSON** with the standard field names as keys.

Example output format:
{{
  "Sl.no": "1",
  "Month": "October",
  "Invoice Date": "25-Oct-25",
  "Invoice Name": "Sales Invoice",
  "Invoice No": "INV-2024-1004",
  "GST": "GSTIN 07AAECR2971C1Z3",
  "Vendor Name": "Americon consulting group USA",
  "Total Amount": "456732.21(USD)",
  "Payment status": "",
  "Audit Status": "",
  "Remarks": "",
  "Supporting Docs": ""
}}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert invoice parser. Respond in pure JSON format only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=1200
        )
        result_text = response["choices"][0]["message"]["content"]

        # Ensure valid JSON
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
            data = json.loads(json_match.group(0)) if json_match else {"raw_text": result_text}

        return data

    except Exception as e:
        raise RuntimeError(f"OpenAI extraction failed: {e}")


def update_excel(excel_path: str, extracted_data: dict) -> str:
    """
    Append extracted invoice data to an existing Excel file.
    If the file doesn't exist, create a new one with proper columns.
    Auto-increments 'Sl.no' if not provided.
    Returns path to the updated Excel file.
    
    expected keys in extracted_data:
    ['Sl.no', 'Month', 'Invoice Date', 'Invoice Name', 'Invoice No', 
     'GST', 'Vendor Name', 'Total Amount', 'Payment status', 
     'Audit Status', 'Remarks', 'Supporting Docs']
    """
    try:
        # Load existing Excel or create new with proper columns
        columns = ['Sl.no', 'Month', 'Invoice Date', 'Invoice Name', 'Invoice No',
                   'GST', 'Vendor Name', 'Total Amount', 'Payment status',
                   'Audit Status', 'Remarks', 'Supporting Docs']
        
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
        else:
            df = pd.DataFrame(columns=columns)

        # Auto-increment Sl.no if missing or empty
        if 'Sl.no' not in extracted_data or extracted_data['Sl.no'] == "":
            extracted_data['Sl.no'] = len(df) + 1

        # Ensure extracted_data has all columns
        for col in columns:
            if col not in extracted_data:
                extracted_data[col] = ""  # Fill missing fields with empty string

        # Append new row
        new_row = pd.DataFrame([extracted_data])
        updated_df = pd.concat([df, new_row], ignore_index=True)

        # Save back to Excel
        updated_df.to_excel(excel_path, index=False)
        return excel_path

    except Exception as e:
        raise RuntimeError(f"Excel update failed: {e}")


# ================================
# Django View
# ================================

@csrf_exempt
@require_POST
def upload_invoice(request):
    """
    API endpoint: upload multiple invoice PDFs + Excel, extract data from each, update Excel.
    """
    invoice_files = request.FILES.getlist("invoice")
    excel_file = request.FILES.get("excel")

    if not invoice_files or not excel_file:
        return JsonResponse({"error": "Both 'invoice' (multiple PDFs) and 'excel' files are required."}, status=400)

    invoice_paths = []
    excel_path = None
    all_extracted = []

    try:
        # Save Excel temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as xl_tmp:
            for chunk in excel_file.chunks():
                xl_tmp.write(chunk)
            excel_path = xl_tmp.name

        # Save each invoice PDF temporarily
        for invoice_file in invoice_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as inv_tmp:
                for chunk in invoice_file.chunks():
                    inv_tmp.write(chunk)
                invoice_paths.append(inv_tmp.name)

        # Process each PDF
        for pdf_path in invoice_paths:
            # 1️⃣ OCR extraction
            invoice_text = extract_text_from_pdf_ocr(pdf_path)

            # 2️⃣ GPT extraction
            extracted_data = extract_invoice_data(invoice_text)
            all_extracted.append(extracted_data)

            # 3️⃣ Update Excel
            update_excel(excel_path, extracted_data)

        # Move updated Excel to media dir
        media_excel_path = os.path.join(MEDIA_DIR, os.path.basename(excel_path))
        os.rename(excel_path, media_excel_path)  # Use rename since it's local
        file_url = request.build_absolute_uri(f"/media/{os.path.basename(media_excel_path)}")

        return JsonResponse({
            "message": f"✅ Processed {len(invoice_paths)} invoices successfully.",
            "extracted_data": all_extracted,
            "updated_excel_path": file_url
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    finally:
        # Cleanup temp files
        for invoice_path in invoice_paths:
            if os.path.exists(invoice_path):
                os.remove(invoice_path)
        if excel_path and os.path.exists(excel_path):
            os.remove(excel_path)
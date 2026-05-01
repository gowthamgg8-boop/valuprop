"""
ValUprop.in — AWS S3 Storage Service
backend/s3_service.py

Handles uploading PDF reports to S3 and generating pre-signed
download URLs (expire in 7 days per PRD requirement).

SETUP:
  pip install boto3
  Add AWS credentials to .env (see .env.example)

BUCKET STRUCTURE:
  valuprop-reports/
    reports/
      VUP-00001.pdf
      VUP-00002.pdf
      ...

IAM POLICY NEEDED (minimum):
  {
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::valuprop-reports/*"
    }]
  }
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("valuprop.s3")

AWS_REGION          = os.getenv("AWS_REGION",       "ap-south-1")
AWS_ACCESS_KEY_ID   = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_KEY      = os.getenv("AWS_SECRET_ACCESS_KEY", "")
S3_BUCKET           = os.getenv("S3_BUCKET",        "valuprop-reports")
PDF_URL_EXPIRY_SECS = int(os.getenv("PDF_URL_EXPIRY_SECS", str(7 * 24 * 3600)))  # 7 days


def _get_client():
    """Create boto3 S3 client with configured credentials."""
    try:
        import boto3
        return boto3.client(
            "s3",
            region_name            = AWS_REGION,
            aws_access_key_id      = AWS_ACCESS_KEY_ID     or None,
            aws_secret_access_key  = AWS_SECRET_KEY        or None,
            # If running on EC2/Lambda with an IAM role, omit the keys
            # and boto3 will use the instance profile automatically.
        )
    except ImportError:
        logger.error("boto3 not installed — run: pip install boto3")
        raise


def upload_pdf(pdf_bytes: bytes, valuation_id: int) -> Optional[str]:
    """
    Upload a PDF report to S3.

    Args:
        pdf_bytes:    Raw PDF bytes from pdf_service.generate_pdf()
        valuation_id: DB valuation ID (used as filename)

    Returns:
        S3 key (e.g. "reports/VUP-00001.pdf") on success, None on failure.
    """
    if not AWS_ACCESS_KEY_ID and not _has_instance_role():
        logger.warning("AWS credentials not set — PDF not uploaded to S3")
        return None

    s3_key = f"reports/VUP-{valuation_id:05d}.pdf"

    try:
        client = _get_client()
        client.put_object(
            Bucket      = S3_BUCKET,
            Key         = s3_key,
            Body        = pdf_bytes,
            ContentType = "application/pdf",
            # Server-side encryption
            ServerSideEncryption = "AES256",
            # Cache for 1 hour in browser after download
            CacheControl = "max-age=3600",
            # Metadata
            Metadata = {
                "valuation-id": str(valuation_id),
            },
        )
        logger.info(f"PDF uploaded: s3://{S3_BUCKET}/{s3_key} ({len(pdf_bytes):,} bytes)")
        return s3_key

    except Exception as e:
        logger.error(f"S3 upload failed: val={valuation_id} error={e}")
        return None


def get_presigned_url(s3_key: str, expiry_seconds: int = PDF_URL_EXPIRY_SECS) -> Optional[str]:
    """
    Generate a pre-signed URL for a PDF report.
    URL expires after `expiry_seconds` (default 7 days).

    Args:
        s3_key: The S3 key returned from upload_pdf()
        expiry_seconds: URL lifetime in seconds

    Returns:
        Pre-signed HTTPS URL, or None on failure.
    """
    try:
        client = _get_client()
        url = client.generate_presigned_url(
            "get_object",
            Params = {"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn = expiry_seconds,
        )
        logger.info(f"Pre-signed URL generated: key={s3_key} expiry={expiry_seconds}s")
        return url

    except Exception as e:
        logger.error(f"Pre-signed URL failed: key={s3_key} error={e}")
        return None


def delete_pdf(s3_key: str) -> bool:
    """
    Delete a PDF from S3 (e.g. after refund).
    Returns True on success.
    """
    try:
        client = _get_client()
        client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info(f"PDF deleted: s3://{S3_BUCKET}/{s3_key}")
        return True
    except Exception as e:
        logger.error(f"S3 delete failed: key={s3_key} error={e}")
        return False


def _has_instance_role() -> bool:
    """Check if running on EC2/Lambda with an instance profile."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/iam/info",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "5"},
        )
        urllib.request.urlopen(req, timeout=1)
        return True
    except Exception:
        return False

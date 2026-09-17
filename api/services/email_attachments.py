"""Build proposal PDF attachments or signed download links for email."""

from api.services.document_links import document_download_url
from api.services.google_docs import PDF_ATTACHMENT_LIMIT_BYTES, download_google_doc_pdf, proposal_pdf_filename


async def proposal_pdf_attachment(proposal):
    """Return an email attachment, or a link when the PDF is too large."""
    if not proposal.doc_link:
        return None, None
    _, pdf = await download_google_doc_pdf(proposal.doc_link)
    if len(pdf) <= PDF_ATTACHMENT_LIMIT_BYTES:
        return (proposal_pdf_filename(proposal.title, proposal.committee.name), pdf), None
    return None, document_download_url(proposal.id)

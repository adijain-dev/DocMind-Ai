import fitz  # This is PyMuPDF - for reading PDFs
import yaml  # For reading YAML Swagger files
import json  # For reading JSON Swagger files
import os


def split_text_into_chunks(text, chunk_size=800, overlap=100):
    """
    Takes a long text and splits it into smaller pieces.
    We overlap chunks so that important sentences at boundaries aren't cut off.

    Example: chunk_size=800 means each chunk is ~800 characters
    overlap=100 means consecutive chunks share 100 characters
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Only keep chunks that have meaningful content (more than 50 characters)
        if len(chunk.strip()) > 50:
            chunks.append(chunk.strip())

        # Move forward but go back by overlap amount to get shared context
        start = end - overlap

    return chunks


def parse_pdf(file_path):
    """
    Open a PDF file and extract all text from every page.
    Then split into chunks for storage.
    """
    pdf_document = fitz.open(file_path)
    all_text = ""

    for page_number in range(len(pdf_document)):
        page = pdf_document[page_number]
        page_text = page.get_text()
        all_text += page_text + "\n"

    pdf_document.close()
    return split_text_into_chunks(all_text)


def parse_markdown(file_path):
    """
    Read a Markdown (.md) or plain text (.txt) file.
    Just read the raw text and split into chunks.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        text = file.read()

    return split_text_into_chunks(text)


def parse_swagger(file_path):
    """
    Read a Swagger / OpenAPI file (YAML or JSON format).
    Extract each endpoint as a separate chunk with full details.
    Supports both OpenAPI 3.x and Swagger 2.0.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        raw_content = file.read()

    # Try to parse as JSON first, then as YAML
    try:
        api_data = json.loads(raw_content)
    except Exception:
        try:
            api_data = yaml.safe_load(raw_content)
        except Exception:
            api_data = None

    if not isinstance(api_data, dict):
        return []

    chunks = []

    # Extract Base URL (OpenAPI 3 vs Swagger 2.0)
    base_url = "Not specified"
    servers = api_data.get("servers")
    if isinstance(servers, list) and len(servers) > 0 and isinstance(servers[0], dict):
        base_url = servers[0].get("url", "Not specified")
    elif "host" in api_data:
        schemes = api_data.get("schemes", ["https"])
        scheme = schemes[0] if schemes else "https"
        base_url = f"{scheme}://{api_data.get('host')}{api_data.get('basePath', '')}"

    # Add basic API info as first chunk
    api_info = api_data.get("info", {}) if isinstance(api_data.get("info"), dict) else {}
    basic_info = f"""
API Title: {api_info.get('title', 'Unknown')}
Description: {api_info.get('description', 'No description')}
Version: {api_info.get('version', 'Unknown')}
Base URL: {base_url}
    """.strip()
    chunks.append(basic_info)

    # Add each endpoint as a separate chunk
    all_paths = api_data.get("paths", {})
    if isinstance(all_paths, dict):
        for endpoint_path, methods_info in all_paths.items():
            if not isinstance(methods_info, dict):
                continue

            for http_method, endpoint_details in methods_info.items():
                # Only process actual HTTP methods (skip 'parameters', 'summary', etc.)
                if http_method.lower() not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                    continue

                if not isinstance(endpoint_details, dict):
                    continue

                # Build a human-readable description of this endpoint
                tags = endpoint_details.get('tags', [])
                tags_str = ', '.join(tags) if isinstance(tags, list) else str(tags)
                
                params = endpoint_details.get('parameters', [])
                req_body = endpoint_details.get('requestBody', {})
                responses = endpoint_details.get('responses', {})
                resp_keys = list(responses.keys()) if isinstance(responses, dict) else []

                endpoint_chunk = f"""
Endpoint: {http_method.upper()} {endpoint_path}
Summary: {endpoint_details.get('summary', 'No summary')}
Description: {endpoint_details.get('description', 'No description')}
Tags: {tags_str}
Parameters: {json.dumps(params, indent=2) if isinstance(params, (list, dict)) else str(params)}
Request Body: {json.dumps(req_body, indent=2) if isinstance(req_body, dict) else str(req_body)}
Responses: {json.dumps(resp_keys, indent=2)}
                """.strip()

                chunks.append(endpoint_chunk)

    return chunks


def parse_document(file_path):
    """
    Main function - detect file type and call the right parser.
    Returns a list of text chunks ready to be stored.
    """
    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == ".pdf":
        return parse_pdf(file_path)

    elif file_extension in [".md", ".markdown", ".txt"]:
        return parse_markdown(file_path)

    elif file_extension in [".yaml", ".yml", ".json"]:
        return parse_swagger(file_path)

    else:
        raise ValueError(f"File type '{file_extension}' is not supported. Use PDF, YAML, JSON, or Markdown.")

import os
import re
import requests
from urllib.parse import urlencode, quote_plus
from bs4 import BeautifulSoup
import logging
from infant.tools.file_reader.filereader import parse_pdf
from infant.tools.util import update_pwd_decorator
logger = logging.getLogger(__name__)

def generate_arxiv_search_url(
    keyword: str,
    start_date: str,
    end_date: str,
    subject: str = "cs",  # 可选: cs, math, physics, q-bio, q-fin, stat
    field: str = "title",  # 可选: title, abstract, comments, author, all
    size: int = 50,
    order: str = "-announced_date_first"
) -> str:
    base_url = "https://arxiv.org/search/advanced?"
    subject_param_map = {
        "cs": "classification-computer_science",
        "econ": "classification-economics",
        "eess": "classification-eess",
        "math": "classification-mathematics",
        "physics": "classification-physics",
        "q-bio": "classification-q_bio",
        "q-fin": "classification-q_fin",
        "stat": "classification-statistics"
    }

    params = {
        "advanced": "",
        "terms-0-operator": "AND",
        "terms-0-term": keyword,
        "terms-0-field": field,
        "classification-include_cross_list": "include",
        "date-filter_by": "date_range",
        "date-from_date": start_date,
        "date-to_date": end_date,
        "date-date_type": "submitted_date",
        "abstracts": "show",
        "size": str(size),
        "order": order
    }

    if subject in subject_param_map:
        params[subject_param_map[subject]] = "y"

    return base_url + urlencode(params, quote_via=quote_plus)

@update_pwd_decorator
def search_arxiv(
    keyword: str,
    start_date: str,
    end_date: str,
    subject: str = "cs",  # 可选: cs, math, physics, q-bio, q-fin, stat
    field: str = "title",  # 可选: title, abstract, comments, author, all
) -> str:
    url = generate_arxiv_search_url(
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        subject=subject,
        field=field
    )
    max_results: int = 50
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        return f"[HTTP Error] {e.response.status_code}: {e.response.reason}"
    except requests.exceptions.ConnectionError:
        return "[Connection Error] Failed to connect to arXiv."
    except requests.exceptions.Timeout:
        return "[Timeout Error] The request to arXiv timed out."
    except Exception as e:
        return f"[Unknown Error] {str(e)}"
    soup = BeautifulSoup(response.text, 'html.parser')
    results = soup.select('.arxiv-result')

    if not results:
        return "No results found."

    output = []
    if len(results) > max_results:
        output.append(f"Found {len(results)} results, displaying the first {max_results}:\n")
    for i, result in enumerate(results[:max_results]):
        title = result.select_one('.title').text.strip()
        authors = result.select_one('.authors').text.strip().replace('\n', ' ')

        id_section = result.select_one('.list-title').text
        match = re.search(r'arXiv:\d{4}\.\d{5}', id_section)
        arxiv_id = match.group(0) if match else "N/A"

        entry = (
            f"[{i+1}]\n"
            f"arXiv ID: {arxiv_id}\n"
            f"Title: {title}\n"
            f"Authors: {authors}\n"
        )
        output.append(entry)
    if len(results) > max_results:
        output.append("\n... Please narrow your search range to get accurate results.")

    print("\n".join(output))

@update_pwd_decorator
def download_arxiv_pdf(arxiv_id: str) -> str:
    save_dir = "/workspace"
    arxiv_id_clean = arxiv_id.replace("arXiv:", "").strip()
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id_clean}.pdf"
    local_filename = os.path.join(save_dir, f"{arxiv_id_clean}.pdf")

    try:
        response = requests.get(pdf_url)
        if response.status_code == 200:
            with open(local_filename, "wb") as f:
                f.write(response.content)
            print(f"[✓] Downloaded {arxiv_id} to {local_filename}")
            print(
                "The first page of the PDF is shown to you, ",
                "you can use the parse_pdf(pdf_path: str, page: int) command ", 
                "to check the other pages if you want."
            )
            parse_pdf(local_filename, 1)
            
        else:
            print(f"[✗] Failed to download {arxiv_id}: HTTP {response.status_code}")
    except Exception as e:
        print(f"[✗] Exception while downloading {arxiv_id}: {e}")
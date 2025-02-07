import streamlit as st
import time
from Bio import Entrez
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
from datetime import datetime
from metapub import PubMedFetcher

# Configure Streamlit page
st.set_page_config(page_title="PubMed Article Scraper and Summarizer", layout="wide")

fetch = PubMedFetcher()
# Initialize Gemini API
def initialize_gemini():
    try:
        genai.configure(api_key="AIzaSyDq6W2I7bOJHAcEKd3ftLviwqdQDp7WeLc")
        model = genai.GenerativeModel('gemini-pro')
        return model
    except Exception as e:
        st.error(f"Error initializing Gemini API: {str(e)}")
        return None


# Function to get PMIDs
def get_pmids(authors, topics, start_date, end_date, email):
    try:
        Entrez.email = email
        date_range = f'("{start_date}"[Date - Create] : "{end_date}"[Date - Create])'
        queries = []
        if authors:
            author_queries = [f'{author.strip()}[Author]' for author in authors]
            queries.append('(' + ' OR '.join(author_queries) + ')')
        if topics:
            topic_queries = [f'{topic.strip()}[Title/Abstract]' for topic in topics]
            queries.append('(' + ' OR '.join(topic_queries) + ')')
        full_query = ' AND '.join(queries) + ' AND ' + date_range
        # articles = fetch.pmids_for_query('author:"Smith J" AND title:"cancer"')
        handle = Entrez.esearch(db='pubmed', retmax=10, term=full_query)
        record = Entrez.read(handle)
        handle.close()
        return record.get("IdList", [])
    except Exception as e:
        st.error(f"Error fetching PMIDs: {str(e)}")
        return []

# for pmid in get_pmids():
#
#     article = fetch.article_by_pmid(pmid)
#     print(f"Title: {article.title}")
#     print(f"Authors: {', '.join(article.authors)}")
#     print(f"Journal: {article.journal}")
#     print(f"DOI: {article.doi}")
#     print(f"Abstract: {article.abstract}")
#     print()


# Function to convert PMID to PMCID
def convert_to_pmcid(pmid):
    try:
        handle = Entrez.elink(dbfrom="pubmed", db="pmc", id=pmid)
        record = Entrez.read(handle)
        handle.close()
        return f"PMC{record[0]['LinkSetDb'][0]['Link'][0]['Id']}" if record[0]['LinkSetDb'] else None
    except Exception as e:
        st.error(f"Error converting PMID {pmid} to PMCID: {str(e)}")
        return None


# Function to scrape article content
def scrape_article(pmcid):
    try:
        url = f'https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/'
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"}
        webpage = requests.get(url, headers=headers)
        soup = BeautifulSoup(webpage.text, 'html.parser')

        title = soup.find('h1', {'class': 'content-title'})
        journal = soup.find('div', {'class': 'journal-title'})
        authors_div = soup.find('div', {'class': 'contrib-group'})
        full_text = "\n\n".join([p.text.strip() for p in soup.find_all('p')])

        return {
            'title': title.text.strip() if title else "Title not found",
            'journal': journal.text.strip() if journal else "Journal not found",
            'authors': ", ".join(
                [a.text.strip() for a in authors_div.find_all('a')]) if authors_div else "Authors not found",
            'full_text': full_text,
            'pubmed_link': f"https://pubmed.ncbi.nlm.nih.gov/{pmcid.replace('PMC', '')}/"
        }
    except Exception as e:
        st.error(f"Error scraping article {pmcid}: {str(e)}")
        return None


# Function to generate summary using Gemini
def generate_summary(text, model):
    try:
        response = model.generate_content(f"Give the brief overview of this scientific article full text: {text}")
        return response.text if response else "Summary generation failed"
    except Exception as e:
        st.error(f"Error generating summary: {str(e)}")
        return "Summary generation failed"


# Main Streamlit app
def main():
    st.title("PubMed Article Scraper and Summarizer")
    model = initialize_gemini()

    with st.form("search_form"):
        email = st.text_input("Your email (required for PubMed API)", key="email")
        authors = st.text_area("Authors (one per line)", key="authors")
        topics = st.text_area("Topics (one per line)", key="topics")
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Start Date", key="start_date")
        end_date = col2.date_input("End Date", key="end_date")
        submit_button = st.form_submit_button("Search Articles")

    if submit_button and email:
        author_list = [a.strip() for a in authors.split('\n') if a.strip()]
        topic_list = [t.strip() for t in topics.split('\n') if t.strip()]
        start_date_str, end_date_str = start_date.strftime("%Y/%m/%d"), end_date.strftime("%Y/%m/%d")

        with st.spinner("Searching for articles..."):
            pmids = get_pmids(author_list, topic_list, start_date_str, end_date_str, email)
            if pmids:
                st.success(f"Found {len(pmids)} articles")
                for pmid in pmids:
                    with st.spinner(f"Processing article {pmid}..."):
                        pmcid = convert_to_pmcid(pmid)
                        if pmcid:
                            article = fetch.article_by_pmid(pmid)
                            # print(f"Title: {article.title}")
                            # print(f"Authors: {', '.join(article.authors)}")
                            # print(f"Journal: {article.journal}")
                            # print(f"DOI: {article.doi}")
                            # print(f"Abstract: {article.abstract}")
                            # print()
                            article_data = scrape_article(pmcid)
                            if article_data:
                                st.subheader(f"📄 {article.title}")
                                st.write(f"**Journal:** {article.journal}")
                                st.write(f"**Authors:** {', '.join(article.authors)}")
                                st.write(f"**Abstract:** {article.abstract}")
                                st.write(
                                    f"**PubMed Link:** https://pubmed.ncbi.nlm.nih.gov/{pmid}/")

                                if model:
                                    with st.spinner("Generating summary..."):
                                        summary = generate_summary(article_data['full_text'], model)
                                        st.write("**Summary:**")
                                        st.write(summary)
                                st.button(f"Show Full Text: {article_data['title']}", key=f"btn_{pmcid}")
                                st.text_area("Full Article Text", article_data['full_text'], height=300, disabled=True)
                        time.sleep(2)
            else:
                st.warning("No articles found matching your criteria")
    elif submit_button and not email:
        st.error("Please provide your email address")


if __name__ == "__main__":
    main()

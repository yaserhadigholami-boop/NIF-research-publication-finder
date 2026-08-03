import streamlit as st
import pandas as pd
import requests
import re
import difflib
import io
import os

from bs4 import BeautifulSoup
import fitz


# ======================================================
# STREAMLIT CONFIG
# ======================================================

st.set_page_config(
    page_title="NIF Publication Finder",
    layout="wide"
)


st.title("📚 NIF Publication Finder v2.0")



# ======================================================
# USER SETTINGS
# ======================================================

with st.sidebar:

    st.header("Search Settings")


    AUTHOR_NAME = st.text_input(
        "Author name",
        placeholder="Enter author full name"
    )


    ORCID = st.text_input(
        "ORCID (optional)",
        placeholder="https://orcid.org/xxxx"
    )


    INSTITUTION = st.text_input(
        "Institution (optional)",
        placeholder="University name"
    )


    COUNTRY = st.text_input(
        "Country (optional)",
        placeholder="Australia"
    )


col1, col2 = st.columns(2)

with col1:

    START_YEAR = st.number_input(
        "From year",
        min_value=1900,
        max_value=2026,
        value=2011,
        step=1
    )


with col2:

    END_YEAR = st.number_input(
        "To year",
        min_value=1900,
        max_value=2026,
        value=2026,
        step=1
    )


    keyword_text = st.text_area(
        "Keywords",
        """
Brain and Mind
BMC
Sydney Imaging
University of Sydney MRI
Siemens 3T
3T
3 Tesla
MRI
PET-MR
PET MRI
nanoparticle
radiolabel
"""
    )


    KEYWORDS = [

        k.strip()

        for k in keyword_text.split("\n")

        if k.strip()

    ]


    run_button = st.button(
        "🔍 Search"
    )



# ======================================================
# NAME FUNCTIONS
# ======================================================

def clean_name(name):

    name = name.lower()

    name = re.sub(
        r"[^a-z ]",
        "",
        name
    )

    return name.strip()



def name_score(
    target,
    candidate
):

    return int(

        difflib.SequenceMatcher(

            None,

            clean_name(target),

            clean_name(candidate)

        ).ratio()*100

    )



# ======================================================
# OPENALEX AUTHOR SEARCH
# ======================================================

def search_openalex_authors(name):


    url = "https://api.openalex.org/authors"


    params = {

        "search": name,

        "per_page": 25

    }


    r = requests.get(

        url,

        params=params,

        timeout=60

    )


    return r.json().get(

        "results",

        []

    )



# ======================================================
# AUTHOR SCORING
# ======================================================

def score_author(author):


    score = 0


    name = author.get(
        "display_name",
        ""
    )


    score += name_score(
        AUTHOR_NAME,
        name
    )



    # ORCID

    if ORCID:


        author_orcid = author.get(
            "orcid"
        )


        if author_orcid:


            if ORCID.lower() in author_orcid.lower():

                score += 100




    # Institutions

    last_institutions = author.get(
        "last_known_institutions"
    )


    institutions = []


    if isinstance(
        last_institutions,
        list
    ):


        for inst in last_institutions:


            if isinstance(
                inst,
                dict
            ):


                institutions.append(

                    inst.get(
                        "display_name",
                        ""
                    ).lower()

                )



    inst_text = " ".join(
        institutions
    )



    if INSTITUTION:


        if INSTITUTION.lower() in inst_text:

            score += 40



    if "sydney" in inst_text:

        score += 20




    # Country

    if isinstance(
        last_institutions,
        list
    ):


        for inst in last_institutions:


            if isinstance(
                inst,
                dict
            ):


                if inst.get(
                    "country_code",
                    ""
                ) == "AU":

                    score += 20



    return score




# ======================================================
# FIND AUTHOR
# ======================================================

def find_best_author(
    progress,
    status
):


    status.info(
        "Searching OpenAlex author profiles..."
    )


    candidates = search_openalex_authors(
        AUTHOR_NAME
    )


    if len(candidates) == 0:

        return None



    ranked=[]


    for i,a in enumerate(candidates):


        ranked.append(

            (
                score_author(a),
                a
            )

        )


        progress.progress(
            int(
                (i+1)/len(candidates)*20
            )
        )



    ranked.sort(

        key=lambda x:x[0],

        reverse=True

    )


    return ranked[0][1]

# ======================================================
# PUBLICATION RETRIEVAL
# ======================================================


def get_openalex_works(
    author_id,
    progress,
    status
):


    status.info(
        "Searching OpenAlex publications..."
    )


    author_id = author_id.replace(
        "https://openalex.org/",
        ""
    )


    url = "https://api.openalex.org/works"



    params = {


        "filter":

        f"author.id:{author_id},"
        f"from_publication_date:{START_YEAR}-01-01,"
        f"to_publication_date:{END_YEAR}-12-31",


        "per_page":200,


        "sort":
        "publication_date:desc"

    }



    r = requests.get(

        url,

        params=params,

        timeout=60

    )



    return r.json().get(

        "results",

        []

    )




# ======================================================
# CROSSREF
# ======================================================


def get_crossref_works():



    url = "https://api.crossref.org/works"



    params = {


        "query.author":
        AUTHOR_NAME,


        "rows":
        100,


        "filter":

        f"from-pub-date:{START_YEAR}-01-01,"
        f"until-pub-date:{END_YEAR}-12-31"

    }



    try:


        r = requests.get(

            url,

            params=params,

            timeout=60

        )


        return r.json()["message"]["items"]



    except:


        return []






def convert_crossref(item):


    title = ""


    if item.get("title"):

        title = item["title"][0]



    year = ""



    if item.get(
        "published-print"
    ):


        year = item["published-print"]["date-parts"][0][0]


    elif item.get(
        "published-online"
    ):


        year = item["published-online"]["date-parts"][0][0]



    doi = ""


    if item.get("DOI"):

        doi = (

            "https://doi.org/"

            +

            item["DOI"]

        )



    return {


        "title":
        title,


        "publication_year":
        year,


        "doi":
        doi,


        "source":
        "Crossref"

    }







# ======================================================
# MERGE DATABASES
# ======================================================


def merge_publications(
    openalex,
    crossref
):


    database={}



    for p in openalex:


        key = (

            p.get(
                "doi"
            )

            or

            p.get(
                "title",
                ""
            ).lower()

        )


        database[key]=p





    for item in crossref:


        p = convert_crossref(
            item
        )


        key = (

            p.get(
                "doi"
            )

            or

            p.get(
                "title",
                ""
            ).lower()

        )



        if key not in database:


            database[key]=p



    return list(
        database.values()
    )






# ======================================================
# ABSTRACT EXTRACTION
# ======================================================


def extract_openalex_abstract(work):


    inv = work.get(
        "abstract_inverted_index"
    )


    if not inv:

        return ""



    words=[]



    for word,positions in inv.items():


        for p in positions:


            words.append(

                (
                    p,
                    word
                )

            )



    words.sort()



    return " ".join(

        [

            x[1]

            for x in words

        ]

    ).lower()






# ======================================================
# PDF EXTRACTION
# ======================================================


def find_pdf(work):


    locations=[]


    if work.get(
        "best_oa_location"
    ):


        locations.append(

            work["best_oa_location"]

        )


    locations.extend(

        work.get(
            "locations",
            []
        )

    )



    for loc in locations:


        if loc.get(
            "pdf_url"
        ):


            return loc["pdf_url"]



    return None






def read_pdf(url):


    try:


        r = requests.get(

            url,

            timeout=60

        )



        filename="temp.pdf"



        with open(
            filename,
            "wb"
        ) as f:


            f.write(
                r.content
            )



        doc = fitz.open(
            filename
        )


        text=""


        for page in doc:


            text += page.get_text()



        doc.close()


        os.remove(
            filename
        )


        return text.lower()



    except:


        return ""







def get_full_text(work):


    text = extract_openalex_abstract(
        work
    )


    pdf = find_pdf(
        work
    )


    if pdf:


        text += "\n"

        text += read_pdf(
            pdf
        )


    return text.lower()

# ======================================================
# KEYWORD SEARCH
# ======================================================


def find_keywords(text):


    found=[]

    evidence=[]


    text=text.lower()



    sentences=re.split(

        r"[.!?]",

        text

    )



    for keyword in KEYWORDS:


        k = keyword.lower()



        if k in text:


            found.append(
                keyword
            )


            for sentence in sentences:


                if k in sentence:


                    evidence.append(

                        sentence.strip()

                    )


                    break



    return found,evidence





# ======================================================
# AUTHOR CONFIRMATION
# ======================================================


def calculate_author_score(work):


    score=0


    authors=[]


    for a in work.get(
        "authorships",
        []
    ):


        author=a.get(
            "author",
            {}
        )


        authors.append(

            author.get(
                "display_name",
                ""
            )

        )



    combined=" ".join(
        authors
    ).lower()



    target=AUTHOR_NAME.lower()



    if target in combined:


        score+=100


    else:


        for part in target.split():


            if part in combined:

                score+=20



    return score






# ======================================================
# ANALYSE PAPERS
# ======================================================


def analyse_papers(
    papers,
    progress,
    status
):


    results=[]


    total=len(papers)



    for i,paper in enumerate(papers):


        status.info(

            f"Analysing publication {i+1}/{total}"

        )


        author_score = calculate_author_score(
            paper
        )


        if author_score < 40:


            progress.progress(

                20 + int(
                    (i+1)/total*80
                )

            )


            continue



        text=get_full_text(
            paper
        )


        keywords,evidence=find_keywords(
            text
        )



        if len(keywords)>0:


            results.append({


                "Year":

                paper.get(
                    "publication_year",
                    ""
                ),



                "Title":

                paper.get(
                    "title",
                    ""
                ),



                "Author score":

                author_score,



                "Keywords found":

                ", ".join(
                    keywords
                ),



                "Evidence":

                " | ".join(
                    evidence
                ),



                "DOI":

                paper.get(
                    "doi",
                    ""
                )

            })



        progress.progress(

            20 + int(
                (i+1)/total*80
            )

        )



    return pd.DataFrame(
        results
    )





# ======================================================
# MAIN STREAMLIT PIPELINE
# ======================================================


if run_button:


    if not AUTHOR_NAME.strip():


        st.error(
            "Please enter an author name."
        )


        st.stop()



    progress = st.progress(
        0
    )


    status = st.empty()



    # -----------------------------
    # Author search
    # -----------------------------


    author=find_best_author(

        progress,

        status

    )



    if author is None:


        st.error(
            "No matching author found."
        )


        st.stop()



    st.success(

        f"Selected author: {author.get('display_name')}"

    )



    st.write(

        "OpenAlex ID:",

        author.get("id")

    )



    # -----------------------------
    # Publications
    # -----------------------------


    openalex=get_openalex_works(

        author.get("id"),

        progress,

        status

    )



    crossref=get_crossref_works()



    papers=merge_publications(

        openalex,

        crossref

    )



    st.info(

        f"Total publications found: {len(papers)}"

    )



    # -----------------------------
    # Analysis
    # -----------------------------


    df=analyse_papers(

        papers,

        progress,

        status

    )



    progress.progress(
        100
    )


    status.success(
        "Search completed"
    )



    # -----------------------------
    # Results
    # -----------------------------


    st.subheader(
        "Matching Publications"
    )



    if len(df)>0:


        st.dataframe(

            df,

            use_container_width=True

        )



        csv=df.to_csv(
            index=False
        )



        st.download_button(

            "Download CSV",

            csv,

            "publication_results.csv",

            "text/csv"

        )



        excel_buffer=io.BytesIO()



        df.to_excel(

            excel_buffer,

            index=False

        )



        st.download_button(

            "Download Excel",

            excel_buffer.getvalue(),

            "publication_results.xlsx"

        )



    else:


        st.warning(

            "No publications matched the selected keywords."

        )

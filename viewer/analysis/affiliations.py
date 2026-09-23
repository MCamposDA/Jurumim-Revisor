import re

# =====================================================
# Countries and the names used for them in affiliations
# =====================================================
# Entries are regex fragments matched case-insensitively and only as whole
# words. ACRONYMS are matched case-sensitively so "uk" or "usa" inside other
# words never count.

COUNTRY_NAMES = {
    "Afghanistan": ["Afghanistan"],
    "Albania": ["Albania"],
    "Algeria": ["Algeria", "Alg[ée]rie"],
    "Andorra": ["Andorra"],
    "Angola": ["Angola"],
    "Antigua and Barbuda": ["Antigua and Barbuda", "Antigua"],
    "Argentina": ["Argentina"],
    "Armenia": ["Armenia"],
    "Australia": ["Australia"],
    "Austria": ["Austria", "[ÖO]sterreich"],
    "Azerbaijan": ["Azerbaijan"],
    "Bahamas": ["Bahamas"],
    "Bahrain": ["Bahrain"],
    "Bangladesh": ["Bangladesh"],
    "Barbados": ["Barbados"],
    "Belarus": ["Belarus"],
    "Belgium": ["Belgium", "Belgique", "Belgi[eë]"],
    "Belize": ["Belize"],
    "Benin": ["Benin", "B[ée]nin"],
    "Bhutan": ["Bhutan"],
    "Bolivia": ["Bolivia"],
    "Bosnia and Herzegovina": ["Bosnia and Herzegovina", "Bosnia"],
    "Botswana": ["Botswana"],
    "Brazil": ["Brazil", "Brasil"],
    "Brunei": ["Brunei"],
    "Bulgaria": ["Bulgaria"],
    "Burkina Faso": ["Burkina Faso"],
    "Burundi": ["Burundi"],
    "Cabo Verde": ["Cabo Verde", "Cape Verde"],
    "Cambodia": ["Cambodia"],
    "Cameroon": ["Cameroon", "Cameroun"],
    "Canada": ["Canada"],
    "Central African Republic": ["Central African Republic"],
    "Chad": ["Chad", "Tchad"],
    "Chile": ["Chile"],
    "China": ["China", "People'?s Republic of China"],
    "Colombia": ["Colombia", "Col[ôo]mbia"],
    "Comoros": ["Comoros"],
    "Congo": ["Republic of (?:the )?Congo", "Congo"],
    "DR Congo": ["Democratic Republic of (?:the )?Congo", "DR Congo", "D\\.R\\. Congo"],
    "Costa Rica": ["Costa Rica"],
    "Côte d'Ivoire": ["C[ôo]te d.Ivoire", "Ivory Coast"],
    "Croatia": ["Croatia"],
    "Cuba": ["Cuba"],
    "Cyprus": ["Cyprus"],
    "Czech Republic": ["Czech Republic", "Czechia"],
    "Denmark": ["Denmark"],
    "Djibouti": ["Djibouti"],
    "Dominica": ["Dominica"],
    "Dominican Republic": ["Dominican Republic", "Rep[úu]blica Dominicana"],
    "Ecuador": ["Ecuador", "Equador"],
    "Egypt": ["Egypt"],
    "El Salvador": ["El Salvador"],
    "Equatorial Guinea": ["Equatorial Guinea"],
    "Eritrea": ["Eritrea"],
    "Estonia": ["Estonia"],
    "Eswatini": ["Eswatini", "Swaziland"],
    "Ethiopia": ["Ethiopia"],
    "Fiji": ["Fiji"],
    "Finland": ["Finland"],
    "France": ["France"],
    "French Guiana": ["French Guiana", "Guyane"],
    "Gabon": ["Gabon"],
    "Gambia": ["Gambia"],
    "Georgia": ["Georgia"],
    "Germany": ["Germany", "Deutschland"],
    "Ghana": ["Ghana"],
    "Greece": ["Greece"],
    "Grenada": ["Grenada"],
    "Guadeloupe": ["Guadeloupe"],
    "Guatemala": ["Guatemala"],
    "Guinea": ["Guinea", "Guin[ée]e"],
    "Guinea-Bissau": ["Guinea-Bissau", "Guin[ée]-Bissau"],
    "Guyana": ["Guyana"],
    "Haiti": ["Haiti"],
    "Honduras": ["Honduras"],
    "Hong Kong": ["Hong Kong"],
    "Hungary": ["Hungary"],
    "Iceland": ["Iceland"],
    "India": ["India"],
    "Indonesia": ["Indonesia"],
    "Iran": ["Iran"],
    "Iraq": ["Iraq"],
    "Ireland": ["Ireland", "Eire"],
    "Israel": ["Israel"],
    "Italy": ["Italy", "Italia"],
    "Jamaica": ["Jamaica"],
    "Japan": ["Japan"],
    "Jordan": ["Jordan"],
    "Kazakhstan": ["Kazakhstan"],
    "Kenya": ["Kenya"],
    "Kiribati": ["Kiribati"],
    "Kosovo": ["Kosovo"],
    "Kuwait": ["Kuwait"],
    "Kyrgyzstan": ["Kyrgyzstan", "Kyrgyz Republic"],
    "Laos": ["Laos", "Lao PDR", "Lao People'?s Democratic Republic"],
    "Latvia": ["Latvia"],
    "Lebanon": ["Lebanon"],
    "Lesotho": ["Lesotho"],
    "Liberia": ["Liberia"],
    "Libya": ["Libya"],
    "Liechtenstein": ["Liechtenstein"],
    "Lithuania": ["Lithuania"],
    "Luxembourg": ["Luxembourg"],
    "Macau": ["Maca[ou]"],
    "Madagascar": ["Madagascar"],
    "Malawi": ["Malawi"],
    "Malaysia": ["Malaysia"],
    "Maldives": ["Maldives"],
    "Mali": ["Mali"],
    "Malta": ["Malta"],
    "Marshall Islands": ["Marshall Islands"],
    "Martinique": ["Martinique"],
    "Mauritania": ["Mauritania"],
    "Mauritius": ["Mauritius"],
    "Mexico": ["(?<!New )M[ée]xico"],
    "Micronesia": ["Micronesia"],
    "Moldova": ["Moldova"],
    "Monaco": ["Monaco"],
    "Mongolia": ["Mongolia"],
    "Montenegro": ["Montenegro"],
    "Morocco": ["Morocco", "Maroc"],
    "Mozambique": ["Mozambique", "Mo[çc]ambique"],
    "Myanmar": ["Myanmar", "Burma"],
    "Namibia": ["Namibia"],
    "Nauru": ["Nauru"],
    "Nepal": ["Nepal"],
    "Netherlands": ["Netherlands", "Holland", "Nederland"],
    "New Caledonia": ["New Caledonia", "Nouvelle-Cal[ée]donie"],
    "New Zealand": ["New Zealand"],
    "Nicaragua": ["Nicaragua"],
    "Niger": ["Niger"],
    "Nigeria": ["Nigeria"],
    "North Korea": ["North Korea", "Democratic People'?s Republic of Korea", "DPR Korea"],
    "North Macedonia": ["North Macedonia", "Macedonia"],
    "Norway": ["Norway"],
    "Oman": ["Oman"],
    "Pakistan": ["Pakistan"],
    "Palau": ["Palau"],
    "Palestine": ["Palestine", "Palestinian Territor(?:y|ies)", "Gaza", "West Bank"],
    "Panama": ["Panam[aá]"],
    "Papua New Guinea": ["Papua New Guinea"],
    "Paraguay": ["Paraguay", "Paraguai"],
    "Peru": ["Peru", "Per[úu]"],
    "Philippines": ["Philippines"],
    "Poland": ["Poland", "Polska"],
    "Portugal": ["Portugal"],
    "Puerto Rico": ["Puerto Rico"],
    "Qatar": ["Qatar"],
    "Réunion": ["R[ée]union Island", "La R[ée]union"],
    "Romania": ["Romania"],
    "Russia": ["Russia", "Russian Federation"],
    "Rwanda": ["Rwanda"],
    "Saint Kitts and Nevis": ["Saint Kitts and Nevis"],
    "Saint Lucia": ["Saint Lucia"],
    "Saint Vincent and the Grenadines": ["Saint Vincent and the Grenadines"],
    "Samoa": ["Samoa"],
    "San Marino": ["San Marino"],
    "Sao Tome and Principe": ["S[ãa]o Tom[ée] and Pr[íi]ncipe"],
    "Saudi Arabia": ["Saudi Arabia", "Kingdom of Saudi Arabia"],
    "Senegal": ["Senegal", "S[ée]n[ée]gal"],
    "Serbia": ["Serbia"],
    "Seychelles": ["Seychelles"],
    "Sierra Leone": ["Sierra Leone"],
    "Singapore": ["Singapore"],
    "Slovakia": ["Slovakia", "Slovak Republic"],
    "Slovenia": ["Slovenia"],
    "Solomon Islands": ["Solomon Islands"],
    "Somalia": ["Somalia"],
    "South Africa": ["South Africa"],
    "South Korea": ["South Korea", "Republic of Korea", "Korea"],
    "South Sudan": ["South Sudan"],
    "Spain": ["Spain", "Espa[ñn]a"],
    "Sri Lanka": ["Sri Lanka"],
    "Sudan": ["Sudan"],
    "Suriname": ["Suriname?"],
    "Sweden": ["Sweden", "Sverige"],
    "Switzerland": ["Switzerland", "Suisse", "Schweiz", "Svizzera"],
    "Syria": ["Syria", "Syrian Arab Republic"],
    "Taiwan": ["Taiwan"],
    "Tajikistan": ["Tajikistan"],
    "Tanzania": ["Tanzania"],
    "Thailand": ["Thailand"],
    "Timor-Leste": ["Timor-Leste", "East Timor"],
    "Togo": ["Togo"],
    "Tonga": ["Tonga"],
    "Trinidad and Tobago": ["Trinidad and Tobago", "Trinidad"],
    "Tunisia": ["Tunisia", "Tunisie"],
    "Turkey": ["Turkey", "T[üu]rkiye"],
    "Turkmenistan": ["Turkmenistan"],
    "Tuvalu": ["Tuvalu"],
    "Uganda": ["Uganda"],
    "Ukraine": ["Ukraine"],
    "United Arab Emirates": ["United Arab Emirates"],
    "United Kingdom": ["United Kingdom", "England", "Scotland", "(?<!New South )Wales",
                       "Northern Ireland", "Great Britain"],
    "United States": ["United States(?: of America)?",
                      # State names, for affiliations that omit the country.
                      # Georgia is left out on purpose (also a country).
                      "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
                      "Connecticut", "Delaware", "Florida", "Hawaii", "Idaho", "Illinois",
                      "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
                      "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
                      "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
                      "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
                      "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
                      "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
                      "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin",
                      "Wyoming"],
    "Uruguay": ["Uruguay", "Uruguai"],
    "Uzbekistan": ["Uzbekistan"],
    "Vanuatu": ["Vanuatu"],
    "Venezuela": ["Venezuela"],
    "Vietnam": ["Vietnam", "Viet Nam"],
    "Yemen": ["Yemen"],
    "Zambia": ["Zambia"],
    "Zimbabwe": ["Zimbabwe"],
}

ACRONYMS = {
    "United States": [r"USA", r"U\.S\.A\.?", r"U\. S\. A\.?", r"U\.S\."],
    "United Kingdom": [r"UK", r"U\.K\."],
    "United Arab Emirates": [r"UAE"],
    "China": [r"PR China", r"P\.R\. China", r"PRC"],
}


def _compilar():
    padroes = []
    for pais, nomes in COUNTRY_NAMES.items():
        padroes.append((pais, re.compile(r"(?<![\w-])(?:" + "|".join(nomes) + r")(?![\w-])",
                                         re.IGNORECASE)))
    for pais, siglas in ACRONYMS.items():
        padroes.append((pais, re.compile(r"(?<![\w-])(?:" + "|".join(siglas) + r")(?![\w-])")))
    return padroes


_PADROES = _compilar()
_EMAIL = re.compile(r"\S+@\S+|Electronic address:?", re.IGNORECASE)


# =====================================================
# Country from an affiliation string
# =====================================================

def infer_country(affiliation_text):
    """
    Country named in an affiliation, or "Unknown".

    E-mails are removed first. When several countries are named, the one that
    appears last wins (affiliations usually end with the country); on a tie
    the longer name wins ("Papua New Guinea" over "Guinea").
    """
    if not affiliation_text:
        return "Unknown"

    texto = _EMAIL.sub(" ", affiliation_text)
    texto = re.sub(r"\s+", " ", texto)

    melhor, fim_melhor, tam_melhor = "Unknown", -1, 0
    for pais, padrao in _PADROES:
        for m in padrao.finditer(texto):
            fim, tam = m.end(), m.end() - m.start()
            if fim > fim_melhor or (fim == fim_melhor and tam > tam_melhor):
                melhor, fim_melhor, tam_melhor = pais, fim, tam
    return melhor


# =====================================================
# Affiliations of an article
# =====================================================

def extract_affiliations(article):
    """All AD lines of the article as a list (C1 kept for Web of Science exports)."""
    for tag in ("C1", "AD"):
        valor = article.get(tag)
        if valor:
            return valor if isinstance(valor, list) else [valor]
    return []


def _country_of_author(afiliacoes):
    """First recognized country among one author's affiliations."""
    for af in afiliacoes:
        pais = infer_country(af)
        if pais != "Unknown":
            return pais
    return "Unknown"


def get_author_nationalities(article):
    """
    Country of the first and last authors, each taken only from that
    author's own AD lines. An author without AD is "Unknown"; affiliations
    are never borrowed from co-authors.
    """
    autores = article.get("FAU", [])
    ad_por_autor = article.get("_AD_BY_AUTHOR", [])

    if not autores or len(ad_por_autor) != len(autores):
        return {
            "primeiro_autor": autores[0] if autores else None,
            "ultimo_autor": autores[-1] if autores else None,
            "pais_primeiro_autor": "Unknown",
            "pais_ultimo_autor": "Unknown",
            "afiliacao_primeiro": None,
            "afiliacao_ultimo": None
        }

    ad_primeiro, ad_ultimo = ad_por_autor[0], ad_por_autor[-1]

    return {
        "primeiro_autor": autores[0],
        "ultimo_autor": autores[-1],
        "pais_primeiro_autor": _country_of_author(ad_primeiro),
        "pais_ultimo_autor": _country_of_author(ad_ultimo),
        "afiliacao_primeiro": ad_primeiro[0] if ad_primeiro else None,
        "afiliacao_ultimo": ad_ultimo[0] if ad_ultimo else None
    }


# =====================================================
# Functions used by the viewer
# =====================================================

def get_author_country(article, author_name):
    """Country of a given author of the article (from that author's own AD lines)."""
    autores = article.get("FAU", [])
    ad_por_autor = article.get("_AD_BY_AUTHOR", [])
    if author_name in autores and len(ad_por_autor) == len(autores):
        return _country_of_author(ad_por_autor[autores.index(author_name)])
    return "Unknown"


def get_article_countries(article):
    """Countries of the first and last authors, keyed 'primeiro' and 'ultimo'."""
    info = get_author_nationalities(article)

    return {
        "primeiro": info.get("pais_primeiro_autor", "Unknown"),
        "ultimo": info.get("pais_ultimo_autor", "Unknown")
    }

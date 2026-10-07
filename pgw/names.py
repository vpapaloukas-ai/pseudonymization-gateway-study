"""Static lists for the synthetic CRM (spec §3). No entry appears in two name lists."""

FIRST_NAMES = [
    "Ada", "Ben", "Chloe", "Daniel", "Eleanor", "Farid", "Gemma", "Harry", "Isla", "James",
    "Kofi", "Laura", "Mohammed", "Nina", "Oliver", "Priya", "Quentin", "Ruth", "Samuel", "Tara",
    "Umar", "Vera", "Wesley", "Xenia", "Yusuf", "Zara", "Alistair", "Bethany", "Callum", "Deborah",
    "Ewan", "Fiona", "Gareth", "Hannah", "Imran", "Joanna", "Kieran", "Leah", "Martin", "Niamh",
]

# First names that are also ordinary English words: the gateway matches them only when capitalised.
WORD_FIRST_NAMES = ["Rose", "Mark", "Will", "Grace", "Hope", "Bill", "Faith", "Joy"]

LAST_NAMES = [
    "Okafor", "Hale", "Whitmore", "Patel", "Brennan", "Ashby", "Calloway", "Dunmore", "Ellison",
    "Fairbairn", "Gallagher", "Hargreaves", "Iqbal", "Jennings", "Kavanagh", "Lindqvist", "Mbeki",
    "Nakamura", "Osei", "Pemberton", "Quigley", "Radcliffe", "Sutherland", "Thackeray", "Underwood",
    "Vasquez", "Wainwright", "Yardley", "Zielinski", "Abernethy", "Blackwood", "Carrick", "Delacroix",
    "Esposito", "Forsythe", "Goldsmith", "Holloway", "Ibrahim", "Jarvis", "Kowalski", "Lockhart",
    "Mortimer", "Nightingale", "Ollerenshaw", "Prendergast", "Rahman", "Sinclair", "Trevelyan",
    "Uddin", "Vickers", "Westbrook", "Achebe", "Barraclough", "Cheung", "Dimitriou", "Eriksen",
    "Fitzgerald", "Gunawardena", "Hutchinson", "Ingram",
]

TITLES = ["Mr", "Ms", "Dr", "Mx"]

TOWNS = [
    "Whitby", "Ludlow", "Hexham", "Kendal", "Bude", "Penrith", "Malton", "Totnes", "Frome", "Morpeth",
    "Ripon", "Alnwick", "Bakewell", "Ledbury", "Thirsk", "Beverley", "Skipton", "Dorking", "Romsey",
    "Sherborne", "Tewkesbury", "Kelso", "Oakham", "Lewes", "Bridport", "Keswick", "Buxton", "Stamford",
    "Marlow", "Hythe",
]

# Short forms a customer may sign with. Deliberately NOT in the gateway's variant list (spec §3, §6).
NICKNAMES = {
    "Daniel": "Dan", "Eleanor": "Nell", "James": "Jim", "Mohammed": "Mo", "Oliver": "Ollie",
    "Samuel": "Sam", "Alistair": "Ali", "Bethany": "Beth", "Deborah": "Debs", "Joanna": "Jo",
    "Martin": "Marty", "Fiona": "Fi",
}

# Third parties a customer mentions ("my husband John"): unknown to the gateway (spec §1).
THIRD_PARTY_MALE = ["John", "Peter", "David", "Robert", "Michael"]
THIRD_PARTY_FEMALE = ["Margaret", "Susan", "Helen", "Anne", "Carol"]
THIRD_PARTY_NAMES = THIRD_PARTY_MALE + THIRD_PARTY_FEMALE
RELATIONS = [("my husband", "m"), ("my wife", "f"), ("my neighbour", None), ("my son", "m"), ("my daughter", "f"),
             ("my colleague", None)]

# Why a refund-case customer wants their money back: never damage, never a wrong item (that is damaged_or_wrong).
REFUND_REASONS = ["changed their mind", "it does not fit the space they had in mind", "it was a duplicate gift",
                  "they no longer need it", "the colour does not suit the room"]

STREETS = [
    "Larkspur Road", "Mill Lane", "Church Street", "Station Road", "Orchard Close", "Victoria Terrace",
    "Elm Grove", "Kingsway", "Park Avenue", "Rowan Drive", "Meadow View", "Quarry Hill",
]

# Invented consumer and work domains. They may coincide with real ones; the README says so (spec §3).
MAIL_DOMAINS = ["postbox-mail.co.uk", "letterpost.co.uk", "homemail-uk.co.uk", "inboxly.co.uk"]
WORK_DOMAINS = ["harrowfield-logistics.co.uk", "calderbrook-consulting.co.uk", "northgate-engineering.co.uk",
                "kestrel-health.co.uk", "thornbury-retail.co.uk"]

COMPANY = "Brightwell Home"
COMPANY_DOMAIN = "brightwellhome.co.uk"

# (product, price in pence). Product names stay in clear (spec §5).
PRODUCTS = [
    ("Oak side table", 8900), ("Linen cushion cover", 1800), ("Ceramic table lamp", 4500),
    ("Wool throw", 6500), ("Bamboo bath mat", 2200), ("Glass storage jars, set of 3", 2400),
    ("Cotton duvet cover", 5500), ("Round wall mirror", 7900), ("Jute rug", 12000),
    ("Copper kettle", 6900), ("Stoneware mug set", 3200), ("Rattan laundry basket", 3900),
]

# Published payment-card TEST numbers only (spec §3). Their source is checked in Task 14 (spec §13.4).
TEST_CARDS = ["4111 1111 1111 1111", "5555 5555 5555 4444", "4242 4242 4242 4242", "3782 822463 10005"]

# Initials pairs that are also common dotted abbreviations ("U.K.", "e.g.", "P.S.", "A.I."): a customer with one of
# these initials gets no initials form, or ordinary prose would be masked as the customer (measured 2026-10-05).
DOTTED_ABBREVIATIONS = ("UK", "US", "EG", "IE", "AM", "PM", "NB", "AI", "PS", "OK", "TV", "ID")

#######################################
# This script is used for querying
# mint data information into google 
# spreadsheet
#######################################
import mintapi
import pandas as pd
import numpy as np
import warnings
import time

from re import sub
from decimal import Decimal
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from df2gspread import df2gspread as d2g

### Global Variables
GSPREAD_SCOPE = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
GSPREAD_KEY = <INSERT GSPREAD KEY>
SPREADSHEET_ID = <INSERT SPREADSHEET_ID>
MINT_USERNAME = <INSERT_MINT_USERNAME>
MINT_PASSWORD = <INSERT_MINT_PASSWORD>

def change_timestamp(params):
    if len(params.split(" ")) == 2:
        month = int(time.strptime(params.split(" ")[0], "%b").tm_mon)
        day = int(params.split(" ")[1])
        year = datetime.now().year
        return datetime(year, month, day)
    return datetime.strptime(params, "%m/%d/%y")

def refine_categories(params,data, topN):
    """
    get top 10
    """
    cat = data.groupby("category").sum().sort_values(by = "amount").head(topN).index
    if params not in cat:
        return "Others"
    else:
        return params
    
def create_mint_objs(username, password):
    ## callback to mint API
    mint = mintapi.Mint(
            username,  # Email used to log in to Mint
            password,  # Your password used to log in to mint
            # Optional parameters
            mfa_method='sms',  # Can be 'sms' (default), 'email', or 'soft-token'.
                               # if mintapi detects an MFA request, it will trigger the requested method
                               # and prompt on the command line.
            headless=False,  # Whether the chromedriver should work without opening a
                             # visible window (useful for server-side deployments)
            mfa_input_callback=None,  # A callback accepting a single argument (the prompt)
                                      # which returns the user-inputted 2FA code. By default
                                      # the default Python `input` function is used.
            session_path=None, # Directory that the Chrome persistent session will be written/read from.
                               # To avoid the 2FA code being asked for multiple times, you can either set
                               # this parameter or log in by hand in Chrome under the same user this runs
                               # as.
            imap_account=None, # account name used to log in to your IMAP server
            imap_password=None, # account password used to log in to your IMAP server
            imap_server=None,  # IMAP server host name
            imap_folder='INBOX',  # IMAP folder that receives MFA email
            wait_for_sync=False,  # do not wait for accounts to sync
            wait_for_sync_timeout=300,  # number of seconds to wait for sync
    )
    return mint

## credit card 
def get_credit_card(transaction_df):
    credit_card = transaction_df[transaction_df["account"] == "CREDIT CARD"][["category", "date", 
                                                                              "account", "omerchant", 
                                                                              "amount"]]
    credit_card["date"] = credit_card["date"].apply(change_timestamp)
    credit_card = credit_card.drop_duplicates(
        subset = ["amount", "omerchant", "category"], keep = "first")
    credit_card = credit_card[credit_card["category"] != "Credit Card Payment"]
    credit_card["amount"] = -1 * credit_card["amount"]
    return credit_card

def get_venmo(transaction_df):
    venmo = transaction_df[transaction_df['account'] == "Venmo"]
    venmo["date"] = venmo["date"].apply(change_timestamp)
    venmo["amount"] = np.where(venmo['category'] != "Income", -1 * venmo["amount"], venmo["amount"])
    venmo = venmo[["category", "date", "account", "omerchant", "amount"]]
    return venmo


def main():
    ## create mint object
    mint = create_mint_objs(MINT_USERNAME, MINT_PASSWORD)
    mint.get_accounts(True)

    # Get transactions
    #mint.get_transactions() # as pandas dataframe
    transaction_json = mint.get_transactions_json(include_investment=False, 
                                                  skip_duplicates=True)

    ## get transaction
    transaction_df = pd.DataFrame(transaction_json)
    transaction_df["amount"] = transaction_df["amount"].apply(lambda x: Decimal(sub(r'[^\d.]', '', x)))
    transaction_df["amount"] = transaction_df["amount"].astype(float)

    print("shaping data")
    credit_card = get_credit_card(transaction_df)
    venmo = get_venmo(transaction_df)

    print("fetching credentials")
    credentials = ServiceAccountCredentials.from_json_keyfile_name(GSPREAD_KEY, GSPREAD_SCOPE)
    gc = gspread.authorize(credentials)

    print("uploading to gsheets")
    d2g.upload(credit_card, SPREADSHEET_ID, "Credit Card", credentials=credentials, row_names=True)
    d2g.upload(venmo, SPREADSHEET_ID, "Venmo", credentials=credentials, row_names=True)

if __name__ == "__main__":
    main()
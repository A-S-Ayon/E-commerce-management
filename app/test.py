import smtplib

EMAIL = "ayon9442@gmail.com"
OLD_APP_PASSWORD = "hndnhpaotmntnlae"  # spaces removed, Gmail ignores them either way

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL, OLD_APP_PASSWORD)
    print("LOGIN SUCCEEDED — old app password is STILL ACTIVE. Revoke it now.")
    server.quit()
except smtplib.SMTPAuthenticationError as e:
    print("LOGIN FAILED — old app password is dead. Good.")
    print(f"Details: {e}")
except Exception as e:
    print(f"Unexpected error (not necessarily auth-related): {e}")
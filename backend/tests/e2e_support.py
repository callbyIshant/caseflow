import os

from tests.test_auth import remove_test_user


def main() -> None:
    customer_email = os.environ.get("CASEFLOW_E2E_CUSTOMER_EMAIL")
    agent_email = os.environ.get("CASEFLOW_E2E_AGENT_EMAIL")
    if customer_email:
        remove_test_user(customer_email)
    if agent_email:
        remove_test_user(agent_email)


if __name__ == "__main__":
    main()

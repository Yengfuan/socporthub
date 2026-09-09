from api.auth import admin_portfolio
from api.models import Committee, Portfolio, ProposalCategory, User
from sqlalchemy import or_


WELFARE_COMMITTEE_NAMES = {
    "Welfare Comm",
    "HeaRHtfelt",
    "Green Commm",
    "Bakers And Cooks",
    "Children",
    "Pioneers",
    "Special Projects",
    "Special Needs",
}


def committee_portfolio(committee: Committee) -> Portfolio:
    return committee.portfolio or (
        Portfolio.welfare if committee.name in WELFARE_COMMITTEE_NAMES else Portfolio.social
    )


def admin_can_access_committee(user: User, committee: Committee) -> bool:
    return user.role.value != "admin" or committee_portfolio(committee) == admin_portfolio(user)


def admin_committee_filter(user: User):
    """SQLAlchemy expression for committees visible to a portfolio admin."""
    target = admin_portfolio(user)
    if target == Portfolio.social:
        return or_(Committee.portfolio == target, Committee.portfolio.is_(None))
    return Committee.portfolio == target


def sends_confirmation_email(committee: Committee, category: ProposalCategory) -> bool:
    return category == ProposalCategory.event or (
        category == ProposalCategory.initiative and committee_portfolio(committee) == Portfolio.welfare
    )

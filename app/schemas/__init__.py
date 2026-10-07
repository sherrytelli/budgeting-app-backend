"""Pydantic schemas package.

Exports all request/response schemas for the API layer.
"""

from app.schemas.analytics import CategoryAnalytics, MonthlyStanding
from app.schemas.auth import Token, TokenData, UserLogin, UserRegister
from app.schemas.budget import (
    CategoryRead,
    MonthlyBudgetBase,
    MonthlyBudgetCreate,
    MonthlyBudgetRead,
    MonthlyBudgetUpdate,
    MonthlyBudgetWithCategories,
)
from app.schemas.category import (
    CategoryWithExpenses,
    DailyCategoryBase,
    DailyCategoryCreate,
    DailyCategoryRead,
    DailyCategoryUpdate,
    ExpenseRead as CategoryExpenseRead,
)
from app.schemas.expense import (
    ExpenseBase,
    ExpenseCreate,
    ExpenseFilter,
    ExpenseRead,
    ExpenseUpdate,
)
from app.schemas.user import UserCreate, UserRead, UserUpdate

__all__ = [
    # Analytics
    "CategoryAnalytics",
    "MonthlyStanding",
    # Auth
    "Token",
    "TokenData",
    "UserLogin",
    "UserRegister",
    # Budget
    "CategoryRead",
    "MonthlyBudgetBase",
    "MonthlyBudgetCreate",
    "MonthlyBudgetRead",
    "MonthlyBudgetUpdate",
    "MonthlyBudgetWithCategories",
    # Category
    "CategoryExpenseRead",
    "CategoryWithExpenses",
    "DailyCategoryBase",
    "DailyCategoryCreate",
    "DailyCategoryRead",
    "DailyCategoryUpdate",
    # Expense
    "ExpenseBase",
    "ExpenseCreate",
    "ExpenseFilter",
    "ExpenseRead",
    "ExpenseUpdate",
    # User
    "UserCreate",
    "UserRead",
    "UserUpdate",
]

from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(index=True, nullable=False)
    name: str
    price: float = 0.0
    stock: int = 0
    min_stock: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class Warehouse(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    location: Optional[str] = None

class StockMovement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    warehouse_id: Optional[int] = Field(default=None, foreign_key="warehouse.id")
    type: str = "adjustment"
    quantity: int = 0
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PurchaseOrderItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    purchase_order_id: Optional[int] = Field(default=None, foreign_key="purchaseorder.id")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    quantity: int = 1
    unit_cost: float = 0.0
    received_quantity: int = 0

class PurchaseOrder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    status: str = "draft"
    total_cost: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    password_hash: str
    role: str = "viewer"

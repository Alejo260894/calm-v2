from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from typing import List, Optional
import pandas as pd, io

from db import engine, create_db_and_tables
from models import Product, Supplier, Warehouse, StockMovement, PurchaseOrder, PurchaseOrderItem, User
import auth as auth_utils

create_db_and_tables()
app = FastAPI(title="Mini ERP PRO")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://calm-frontend.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = auth_utils.decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

@app.post('/token')
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == form_data.username)).first()
        if not user or not auth_utils.verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=400, detail='Incorrect username or password')
        access_token = auth_utils.create_access_token(data={'sub': user.username, 'role': user.role})
        return {'access_token': access_token, 'token_type': 'bearer'}

@app.post('/users/create')
def create_user(username: str = Form(...), password: str = Form(...), role: str = Form('viewer')):
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.username == username)).first()
        if existing:
            raise HTTPException(status_code=400, detail='User exists')
        user = User(username=username, password_hash=auth_utils.get_password_hash(password), role=role)
        session.add(user); session.commit()
        return {'username': user.username, 'role': user.role}

# Helper to enrich PO
def po_to_dict(session, po: PurchaseOrder):
    items = session.exec(select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po.id)).all()
    items_out = []
    for it in items:
        prod = session.get(Product, it.product_id)
        items_out.append({'id': it.id, 'product_id': it.product_id, 'product_name': prod.name if prod else None, 'sku': prod.sku if prod else None, 'quantity': it.quantity, 'unit_cost': it.unit_cost, 'received_quantity': it.received_quantity})
    supplier = session.get(Supplier, po.supplier_id)
    return {'id': po.id, 'supplier_id': po.supplier_id, 'supplier_name': supplier.name if supplier else None, 'status': po.status, 'total_cost': po.total_cost, 'created_at': po.created_at.isoformat(), 'items': items_out}

# Products
@app.post('/products')
def create_product(p: Product, user=Depends(get_current_user)):
    with Session(engine) as session:
        existing = session.exec(select(Product).where(Product.sku == p.sku)).first()
        if existing:
            raise HTTPException(status_code=400, detail='SKU exists')
        session.add(p); session.commit(); session.refresh(p); return p

@app.get('/products', response_model=List[Product])
def list_products(q: Optional[str] = None, user=Depends(get_current_user)):
    with Session(engine) as session:
        prods = session.exec(select(Product)).all()
        if q:
            ql = q.lower(); prods = [p for p in prods if ql in p.name.lower() or ql in p.sku.lower()]
        return prods

# Suppliers / Warehouses
@app.post('/suppliers')
def create_supplier(s: Supplier, user=Depends(get_current_user)):
    with Session(engine) as session:
        session.add(s); session.commit(); session.refresh(s); return s

@app.get('/suppliers', response_model=List[Supplier])
def list_suppliers(user=Depends(get_current_user)):
    with Session(engine) as session:
        return session.exec(select(Supplier)).all()

@app.post('/warehouses')
def create_warehouse(w: Warehouse, user=Depends(get_current_user)):
    with Session(engine) as session:
        session.add(w); session.commit(); session.refresh(w); return w

@app.get('/warehouses', response_model=List[Warehouse])
def list_warehouses(user=Depends(get_current_user)):
    with Session(engine) as session:
        return session.exec(select(Warehouse)).all()

# Purchase Orders
from pydantic import BaseModel
class PurchaseItemCreate(BaseModel):
    product_id: int
    quantity: int
    unit_cost: float

class PurchaseCreate(BaseModel):
    supplier_id: int
    items: List[PurchaseItemCreate]

@app.post('/purchase_orders')
def create_purchase(po: PurchaseCreate, user=Depends(get_current_user)):
    with Session(engine) as session:
        supplier = session.get(Supplier, po.supplier_id)
        if not supplier:
            raise HTTPException(status_code=404, detail='Supplier not found')
        purchase = PurchaseOrder(supplier_id=po.supplier_id, status='ordered', total_cost=0.0)
        session.add(purchase); session.commit(); session.refresh(purchase)
        total = 0.0
        for it in po.items:
            prod = session.get(Product, it.product_id)
            if not prod:
                session.rollback(); raise HTTPException(status_code=404, detail=f'Product {it.product_id} not found')
            poi = PurchaseOrderItem(purchase_order_id=purchase.id, product_id=it.product_id, quantity=it.quantity, unit_cost=it.unit_cost)
            session.add(poi); total += it.quantity * it.unit_cost
        purchase.total_cost = total; session.add(purchase); session.commit(); session.refresh(purchase)
        return po_to_dict(session, purchase)

@app.get('/purchase_orders')
def list_purchase_orders(user=Depends(get_current_user)):
    with Session(engine) as session:
        pos = session.exec(select(PurchaseOrder)).all()
        return [po_to_dict(session, p) for p in pos]

class ReceiveItem(BaseModel):
    purchase_item_id: int
    received_quantity: int

class ReceivePayload(BaseModel):
    warehouse_id: Optional[int] = None
    items: Optional[List[ReceiveItem]] = None

@app.post('/purchase_orders/{po_id}/receive')
def receive_purchase(po_id: int, payload: ReceivePayload, user=Depends(get_current_user)):
    with Session(engine) as session:
        purchase = session.get(PurchaseOrder, po_id)
        if not purchase:
            raise HTTPException(status_code=404, detail='Purchase order not found')
        items = session.exec(select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == purchase.id)).all()
        total_recv = 0
        if payload.items:
            items_map = {it.id: it for it in items}
            for recv in payload.items:
                it = items_map.get(recv.purchase_item_id)
                if not it:
                    raise HTTPException(status_code=400, detail=f'Item {recv.purchase_item_id} not in PO')
                can_add = min(recv.received_quantity, it.quantity - it.received_quantity)
                if can_add <= 0:
                    continue
                it.received_quantity += can_add
                prod = session.get(Product, it.product_id)
                prod.stock += can_add
                session.add(prod); session.add(it)
                mov = StockMovement(product_id=it.product_id, warehouse_id=payload.warehouse_id, type='purchase', quantity=can_add, note=f'Received PO {purchase.id}, item {it.id}')
                session.add(mov); total_recv += can_add
            remaining = session.exec(select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == purchase.id)).all()
            if all(it.received_quantity >= it.quantity for it in remaining):
                purchase.status = 'received'
            session.add(purchase); session.commit(); session.refresh(purchase)
            return {'purchase_order_id': purchase.id, 'received_items': total_recv, 'status': purchase.status}
        else:
            for it in items:
                can_add = it.quantity - it.received_quantity
                if can_add <= 0: continue
                it.received_quantity += can_add
                prod = session.get(Product, it.product_id)
                prod.stock += can_add
                session.add(prod); session.add(it)
                mov = StockMovement(product_id=it.product_id, warehouse_id=payload.warehouse_id, type='purchase', quantity=can_add, note=f'Received PO {purchase.id}, item {it.id}')
                session.add(mov); total_recv += can_add
            purchase.status = 'received'; session.add(purchase); session.commit(); session.refresh(purchase)
            return {'purchase_order_id': purchase.id, 'received_items': total_recv, 'status': purchase.status}

# Stock movements & history
@app.post('/stock/move')
def move_stock(product_id: int = Form(...), quantity: int = Form(...), warehouse_id: Optional[int] = Form(None), type: str = Form('adjustment'), note: Optional[str] = Form(None), user=Depends(get_current_user)):
    with Session(engine) as session:
        prod = session.get(Product, product_id)
        if not prod:
            raise HTTPException(status_code=404, detail='Product not found')
        prod.stock += quantity
        session.add(prod)
        mov = StockMovement(product_id=product_id, warehouse_id=warehouse_id, type=type, quantity=quantity, note=note)
        session.add(mov); session.commit(); session.refresh(mov)
        return mov

@app.get('/stock/movements')
def list_movements(user=Depends(get_current_user)):
    with Session(engine) as session:
        return session.exec(select(StockMovement)).all()

@app.get('/stock/product/{product_id}/movements')
def product_movements(product_id: int, user=Depends(get_current_user)):
    with Session(engine) as session:
        movs = session.exec(select(StockMovement).where(StockMovement.product_id == product_id)).all()
        prod = session.get(Product, product_id)
        return [{'id': m.id, 'type': m.type, 'quantity': m.quantity, 'note': m.note, 'created_at': m.created_at.isoformat(), 'product_name': prod.name if prod else None} for m in movs]

# Inventory low stock
@app.get('/inventory/low')
def low_stock(threshold: Optional[int] = None, user=Depends(get_current_user)):
    with Session(engine) as session:
        if threshold is None:
            return session.exec(select(Product).where(Product.stock <= Product.min_stock)).all()
        return session.exec(select(Product).where(Product.stock <= threshold)).all()

# Import / Export products
@app.post('/import/products')
def import_products(file: UploadFile = File(...), user=Depends(get_current_user)):
    df = pd.read_csv(file.file)
    created = 0
    with Session(engine) as session:
        for _, row in df.iterrows():
            existing = session.exec(select(Product).where(Product.sku == str(row['sku']))).first()
            if existing:
                existing.name = row.get('name', existing.name)
                existing.price = float(row.get('price', existing.price))
                existing.stock = int(row.get('stock', existing.stock))
                existing.min_stock = int(row.get('min_stock', existing.min_stock))
                session.add(existing)
            else:
                prod = Product(sku=str(row['sku']), name=row.get('name',''), price=float(row.get('price',0)), stock=int(row.get('stock',0)), min_stock=int(row.get('min_stock',0)))
                session.add(prod); created += 1
        session.commit()
    return {'imported': created}

from fastapi.responses import StreamingResponse
@app.get('/export/products')
def export_products(user=Depends(get_current_user)):
    with Session(engine) as session:
        prods = session.exec(select(Product)).all()
        df = pd.DataFrame([{'sku':p.sku,'name':p.name,'price':p.price,'stock':p.stock,'min_stock':p.min_stock} for p in prods])
        stream = io.StringIO(); df.to_csv(stream, index=False); stream.seek(0)
        return StreamingResponse(stream, media_type='text/csv', headers={'Content-Disposition':'attachment; filename=products.csv'})

# Dashboard summary
@app.get("/dashboard/summary")
def dashboard_summary():
    with Session(engine) as session:
        products = list(session.exec(select(Product)))
        orders = list(session.exec(select(PurchaseOrder)))

        total_products = len(products)
        total_orders = len(orders)
        total_stock = sum(p.stock for p in products)

        return {
            "total_products": total_products,
            "total_orders": total_orders,
            "total_stock": total_stock
        }

# Seed endpoint
@app.post('/seed')
def seed_default():
    # aseguramos que la BD esté creada antes de insertar
    from db import create_db_and_tables
    create_db_and_tables()

    with Session(engine) as session:
        if session.exec(select(Product)).first():
            return {'status': 'already seeded'}
        try:
            p1 = Product(sku='A1', name='Almohada A', price=49.9, stock=100, min_stock=5)
            p2 = Product(sku='B2', name='Colchón B', price=399.0, stock=10, min_stock=2)
            p3 = Product(sku='C3', name='Sábana C', price=89.5, stock=50, min_stock=5)
            session.add_all([p1, p2, p3])

            s1 = Supplier(name='Proveedor 1', email='prov1@example.com')
            s2 = Supplier(name='Proveedor 2', email='prov2@example.com')
            session.add_all([s1, s2])

            w1 = Warehouse(name='Almacen Central', location='Lima')
            session.add(w1)

            from auth import get_password_hash
            admin = User(username='admin', password_hash=get_password_hash('admin'), role='admin')
            session.add(admin)

            session.commit()
            return {'status': 'seeded'}
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=str(e))


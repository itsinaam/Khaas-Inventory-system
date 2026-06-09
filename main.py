import asyncio
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from database import engine, get_db
from auth import create_access_token, decode_access_token, generate_password, hash_password, verify_password
from models import Base, Inventory, User, Product
from schemas import (
	InventoryCreate,
	InventoryResponse,
	InventoryUpdate,
	LoginRequest,
	TokenResponse,
	UserCreateRequest,
	UserCreateResponse,
	UserResponse,
	ProductCreate,
	ProductResponse,
	ProductUpdate,
)
from typing import List, Optional
from supabase_service import upload_product_image, delete_product_image, get_content_type

app = FastAPI(title="Khaas Inventory Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer()

def create_all_tables() -> None:
	Base.metadata.create_all(bind=engine)


@app.get("/health")
async def health_check():
	return {"status": "healthy"}


@app.post("/create-tables")
async def create_tables():
	await asyncio.to_thread(create_all_tables)
	return {"message": "Database tables created successfully."}


def get_current_user(
	credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
	db: Session = Depends(get_db),
):
	credentials_exception = HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail="Invalid or expired authentication token",
	)

	try:
		payload = decode_access_token(credentials.credentials)
	except ValueError as exc:
		raise credentials_exception from exc

	user = db.query(User).filter(User.id == payload.get("sub")).first()
	if not user or not user.is_active:
		raise credentials_exception

	return user


def get_admin_user(current_user: User = Depends(get_current_user)):
	if current_user.role != "admin":
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Admin access required",
		)
	return current_user


@app.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
	"""Authenticate a user and return a bearer token."""
	user = db.query(User).filter(User.username == payload.username).first()
	if not user or not verify_password(payload.password, user.password_hash):
		raise HTTPException(status_code=401, detail="Invalid username or password")

	if not user.is_active:
		raise HTTPException(status_code=403, detail="User is inactive")

	access_token = create_access_token(user.id, user.username, user.role)
	return TokenResponse(
		access_token=access_token,
		username=user.username,
		role=user.role,
	)


@app.post("/users", response_model=UserCreateResponse, status_code=201)
async def create_user(
	payload: UserCreateRequest,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Admin-only user creation endpoint."""
	_ = current_admin
	if payload.role not in {"admin", "user"}:
		raise HTTPException(status_code=400, detail="Role must be either 'admin' or 'user'")

	existing_user = db.query(User).filter(User.username == payload.username).first()
	if existing_user:
		raise HTTPException(status_code=400, detail="Username already exists")

	plain_password = payload.password or generate_password()
	user = User(
		username=payload.username,
		password_hash=hash_password(plain_password),
		role=payload.role,
	)
	db.add(user)
	db.commit()
	db.refresh(user)

	return UserCreateResponse(
		id=user.id,
		username=user.username,
		role=user.role,
		is_active=user.is_active,
		created_at=user.created_at,
		generated_password=plain_password,
	)


@app.get("/users", response_model=List[UserResponse])
async def list_users(
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Admin-only user listing endpoint."""
	_ = current_admin
	return db.query(User).filter(User.role == "user").order_by(User.id.asc()).all()


@app.delete("/users/{user_id}", status_code=204)
async def delete_user(
	user_id: int,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Admin-only user deletion endpoint."""
	user = db.query(User).filter(User.id == user_id).first()
	if not user:
		raise HTTPException(status_code=404, detail="User not found")

	if user.id == current_admin.id:
		raise HTTPException(status_code=400, detail="Admin cannot delete their own account")

	if user.role == "admin":
		admin_count = db.query(User).filter(User.role == "admin").count()
		if admin_count <= 1:
			raise HTTPException(status_code=400, detail="Cannot delete the last admin user")

	db.delete(user)
	db.commit()
	return None


# ==================== INVENTORY CRUD ENDPOINTS ====================

@app.post("/inventory", response_model=InventoryResponse, status_code=201)
async def create_inventory(
	item: InventoryCreate,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Create a new inventory item"""
	_ = current_admin
	db_item = Inventory(**item.dict())
	db.add(db_item)
	db.commit()
	db.refresh(db_item)
	return db_item


@app.get("/inventory", response_model=List[InventoryResponse])
async def get_all_inventory(
	skip: int = 0,
	limit: int = 100,
	category: str = None,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Get all inventory items with optional filtering"""
	_ = current_admin
	query = db.query(Inventory)
	
	if category:
		query = query.filter(Inventory.category == category)
	
	return query.offset(skip).limit(limit).all()


@app.get("/inventory/{item_id}", response_model=InventoryResponse)
async def get_inventory_item(
	item_id: int,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Get a specific inventory item by ID"""
	_ = current_admin
	db_item = db.query(Inventory).filter(Inventory.id == item_id).first()
	
	if not db_item:
		raise HTTPException(status_code=404, detail="Inventory item not found")
	
	return db_item


@app.put("/inventory/{item_id}", response_model=InventoryResponse)
async def update_inventory_item(
	item_id: int,
	item: InventoryUpdate,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Update an inventory item"""
	_ = current_admin
	db_item = db.query(Inventory).filter(Inventory.id == item_id).first()
	
	if not db_item:
		raise HTTPException(status_code=404, detail="Inventory item not found")
	
	update_data = item.dict(exclude_unset=True)
	for key, value in update_data.items():
		setattr(db_item, key, value)
	
	db.add(db_item)
	db.commit()
	db.refresh(db_item)
	
	return db_item


@app.delete("/inventory/{item_id}", status_code=204)
async def delete_inventory_item(
	item_id: int,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Delete an inventory item"""
	_ = current_admin
	db_item = db.query(Inventory).filter(Inventory.id == item_id).first()
	
	if not db_item:
		raise HTTPException(status_code=404, detail="Inventory item not found")
	
	db.delete(db_item)
	db.commit()
	
	return None

@app.get("/inventory/stats")
async def get_inventory_overview_stats(
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Get overall inventory statistics"""
	_ = current_admin
	
	all_items = db.query(Inventory).all()
	
	total_items = len(all_items)
	low_stock_alert = sum(1 for item in all_items if 0 < item.quantity_received < 10)
	out_of_stock = sum(1 for item in all_items if item.quantity_received == 0)
	
	# Calculate daily valuation (quantity * cost)
	daily_valuation = 0.0
	for item in all_items:
		try:
			cost = float(item.cost) if item.cost else 0.0
			daily_valuation += item.quantity_received * cost
		except (ValueError, TypeError):
			pass
	
	return {
		"total_items": total_items,
		"low_stock_alert": low_stock_alert,
		"out_of_stock": out_of_stock,
		"daily_valuation": round(daily_valuation, 2)
	}


# ==================== PRODUCT CRUD ENDPOINTS ====================

@app.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
	product_name: str = Form(...),
	product_category: str = Form(...),
	product_price: float = Form(...),
	initial_stock: int = Form(...),
	product_photo: Optional[UploadFile] = File(None),
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Create a new product with optional image upload"""
	_ = current_admin
	
	# Handle image upload if provided
	image_url = None
	if product_photo:
		try:
			# Read file content
			file_content = await product_photo.read()
			
			# Determine content type
			content_type = get_content_type(product_photo.filename)
			
			# Upload to Supabase
			image_url = upload_product_image(file_content, product_photo.filename, content_type)
		except Exception as e:
			raise HTTPException(
				status_code=500,
				detail=f"Failed to upload image: {str(e)}"
			)
	
	# Create product in database
	db_product = Product(
		product_name=product_name,
		product_category=product_category,
		product_price=product_price,
		initial_stock=initial_stock,
		product_photo=image_url
	)
	
	db.add(db_product)
	db.commit()
	db.refresh(db_product)
	
	return db_product


@app.get("/products", response_model=List[ProductResponse])
async def get_all_products(
	skip: int = 0,
	limit: int = 100,
	category: Optional[str] = None,
	search: Optional[str] = None,
	min_price: Optional[float] = None,
	max_price: Optional[float] = None,
	min_stock: Optional[int] = None,
	max_stock: Optional[int] = None,
	sort_by: Optional[str] = None,  # Options: name, price, stock, created_at
	sort_order: Optional[str] = "asc",  # Options: asc, desc
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""
	Get all products with advanced filtering options:
	- category: Filter by product category
	- search: Search by product name (partial match)
	- min_price/max_price: Filter by price range
	- min_stock/max_stock: Filter by stock range
	- sort_by: Sort by name, price, stock, or created_at
	- sort_order: asc or desc
	"""
	_ = current_admin
	
	query = db.query(Product)
	
	# Filter by category
	if category:
		query = query.filter(Product.product_category == category)
	
	# Search by product name
	if search:
		query = query.filter(Product.product_name.ilike(f"%{search}%"))
	
	# Filter by price range
	if min_price is not None:
		query = query.filter(Product.product_price >= min_price)
	if max_price is not None:
		query = query.filter(Product.product_price <= max_price)
	
	# Filter by stock range
	if min_stock is not None:
		query = query.filter(Product.initial_stock >= min_stock)
	if max_stock is not None:
		query = query.filter(Product.initial_stock <= max_stock)
	
	# Sorting
	if sort_by:
		if sort_by == "name":
			order_column = Product.product_name
		elif sort_by == "price":
			order_column = Product.product_price
		elif sort_by == "stock":
			order_column = Product.initial_stock
		elif sort_by == "created_at":
			order_column = Product.created_at
		else:
			order_column = Product.id
		
		if sort_order == "desc":
			query = query.order_by(order_column.desc())
		else:
			query = query.order_by(order_column.asc())
	else:
		query = query.order_by(Product.id.desc())
	
	products = query.offset(skip).limit(limit).all()
	return products


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
	product_id: int,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Get a specific product by ID"""
	_ = current_admin
	
	db_product = db.query(Product).filter(Product.id == product_id).first()
	
	if not db_product:
		raise HTTPException(status_code=404, detail="Product not found")
	
	return db_product


@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
	product_id: int,
	product_name: Optional[str] = Form(None),
	product_category: Optional[str] = Form(None),
	product_price: Optional[float] = Form(None),
	initial_stock: Optional[int] = Form(None),
	product_photo: Optional[UploadFile] = File(None),
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Update a product with optional new image"""
	_ = current_admin
	
	db_product = db.query(Product).filter(Product.id == product_id).first()
	
	if not db_product:
		raise HTTPException(status_code=404, detail="Product not found")
	
	# Handle new image upload if provided
	if product_photo:
		try:
			# Delete old image if exists
			if db_product.product_photo:
				delete_product_image(db_product.product_photo)
			
			# Upload new image
			file_content = await product_photo.read()
			content_type = get_content_type(product_photo.filename)
			image_url = upload_product_image(file_content, product_photo.filename, content_type)
			db_product.product_photo = image_url
		except Exception as e:
			raise HTTPException(
				status_code=500,
				detail=f"Failed to upload image: {str(e)}"
			)
	
	# Update other fields if provided
	if product_name is not None:
		db_product.product_name = product_name
	if product_category is not None:
		db_product.product_category = product_category
	if product_price is not None:
		db_product.product_price = product_price
	if initial_stock is not None:
		db_product.initial_stock = initial_stock
	
	db.add(db_product)
	db.commit()
	db.refresh(db_product)
	
	return db_product


@app.delete("/products/{product_id}", status_code=204)
async def delete_product(
	product_id: int,
	db: Session = Depends(get_db),
	current_admin: User = Depends(get_admin_user),
):
	"""Delete a product and its associated image"""
	_ = current_admin
	
	db_product = db.query(Product).filter(Product.id == product_id).first()
	
	if not db_product:
		raise HTTPException(status_code=404, detail="Product not found")
	
	# Delete image from Supabase if exists
	if db_product.product_photo:
		delete_product_image(db_product.product_photo)
	
	db.delete(db_product)
	db.commit()
	
	return None

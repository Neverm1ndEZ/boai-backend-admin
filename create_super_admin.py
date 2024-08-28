from db_operations import create_admin

def create_initial_super_admin():
    email = input("Enter super admin email: ")
    password = input("Enter super admin password: ")
    create_admin(email, password, is_super_admin=True)
    print("Super admin created successfully!")

if __name__ == "__main__":
    create_initial_super_admin()
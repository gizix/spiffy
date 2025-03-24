from app import create_app, db
from app.models import User
import sys


def debug_users():
    app = create_app()
    with app.app_context():
        users = User.query.all()
        print(f"Found {len(users)} users in the database:")

        for user in users:
            print(f"ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Password hash: {user.password_hash[:20]}...")
            print(f"Last login: {user.last_login}")
            print(f"Created at: {user.created_at}")
            print(f"DB path: {user.db_path}")
            print("-" * 40)

        if len(users) == 0:
            print("No users found. Try registering a new user.")

        if (
            len(sys.argv) > 1
            and sys.argv[1] == "--reset-password"
            and len(sys.argv) > 3
        ):
            username = sys.argv[2]
            new_password = sys.argv[3]

            user = User.query.filter_by(username=username).first()
            if user:
                user.set_password(new_password)
                db.session.commit()
                print(f"Password reset for user {username}")
            else:
                print(f"User {username} not found")


if __name__ == "__main__":
    debug_users()

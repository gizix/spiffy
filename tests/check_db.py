from app import create_app, db
from flask_migrate import upgrade


def check_database():
    app = create_app()
    with app.app_context():
        # Check if the database exists and has the required tables
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()

        print(f"Database path: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"Available tables: {existing_tables}")

        expected_tables = ["user", "spotify_data_type", "user_data_sync"]
        missing_tables = [
            table for table in expected_tables if table not in existing_tables
        ]

        if missing_tables:
            print(f"Missing tables: {missing_tables}")

            # Prompt to create tables
            response = input("Would you like to create the missing tables? (y/n): ")
            if response.lower() == "y":
                # Run migrations
                try:
                    db.create_all()
                    print("Tables created successfully")
                except Exception as e:
                    print(f"Error creating tables: {str(e)}")
        else:
            print("All required tables exist")

        # Check number of records in each table
        for table in existing_tables:
            count = db.session.execute(f"SELECT COUNT(*) FROM {table}").scalar()
            print(f"Table {table}: {count} records")


if __name__ == "__main__":
    check_database()

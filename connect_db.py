import mysql.connector

# Database connection parameters (adjust as needed)
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "root"

# Step 1: Connect to MySQL server (default database)
conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Create databasepip install mysql-connector-python
cur.execute("DROP DATABASE IF EXISTS api_test_student;")
cur.execute("CREATE DATABASE api_test_student;")

cur.close()
conn.close()

# Step 2: Connect to the new database
conn = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database="api_test_student"
)
cur = conn.cursor()

# Step 3: Create table
cur.execute("""
    CREATE TABLE student_details (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        age INT NOT NULL,
        course VARCHAR(50) NOT NULL,
        profile_image TEXT,
        rating VARCHAR(10)
    );
""")

# Step 4: Insert records
students = [
    (1, "John Doe", 20, "CS", "https://picsum.photos/200/300", "⭐⭐⭐"),
    (2, "Sarah Lee", 22, "IT", "https://example.com/img17.jpg", "⭐⭐⭐⭐"),
    (3, "Michael Smith", 21, "CS", "https://picsum.photos/200/300", "⭐⭐"),
    (4, "Emily Davis", 23, "IT", "", "⭐⭐⭐⭐⭐"),
    (5, "David Johnson", 19, "CS", "https://picsum.photos/200/300", "⭐⭐⭐"),
    (6, "Sophia Brown", 20, "IT", "", "⭐⭐"),
    (7, "James Wilson", 22, "CS", "", "⭐⭐⭐⭐"),
    (8, "Olivia Taylor", 21, "IT", "https://picsum.photos/200/300", "⭐⭐⭐"),
    (9, "Daniel Martinez", 24, "CS", "", "⭐⭐⭐⭐⭐"),
    (10, "Ava Anderson", 20, "IT", "", "⭐⭐"),
    (11, "Matthew Thomas", 23, "CS", "https://picsum.photos/200/300", "⭐⭐⭐⭐"),
    (12, "Isabella Moore", 19, "IT", "", "⭐⭐⭐"),
    (13, "Christopher Jackson", 21, "CS", "https://example.com/img13.jpg", "⭐⭐⭐⭐⭐"),
    (14, "Mia White", 22, "IT", "", "⭐⭐"),
    (15, "Anthony Harris", 20, "CS", "https://example.com/img15.jpg", "⭐⭐⭐"),
    (16, "Charlotte Martin", 23, "IT", "https://picsum.photos/200/300", "⭐⭐⭐⭐"),
    (17, "Joshua Thompson", 19, "CS", "https://example.com/img17.jpg", "⭐⭐⭐⭐⭐"),
    (18, "Amelia Garcia", 21, "IT", "https://example.com/img18.jpg", "⭐⭐"),
    (19, "Andrew Martinez", 22, "CS", "https://picsum.photos/200/300", "⭐⭐⭐"),
    (20, "Ella Robinson", 20, "IT", "https://example.com/img20.jpg", "⭐⭐⭐⭐"),
    (21, "Joseph Clark", 24, "CS", "https://picsum.photos/200/300", "⭐⭐"),
    (22, "Grace Rodriguez", 19, "IT", "https://picsum.photos/200/300", "⭐⭐⭐⭐⭐")
]

cur.executemany("""
    INSERT INTO student_details (id, name, age, course, profile_image, rating)
    VALUES (%s, %s, %s, %s, %s, %s);
""", students)

# Commit changes and close connection
conn.commit()
cur.close()
conn.close()

print("MySQL database and table created, students inserted successfully!")

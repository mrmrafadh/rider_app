from flask import Flask, jsonify, request
import mysql.connector

app = Flask(__name__)
# Database connection config
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",   # replace with your MySQL password
    "database": "api_test_student"
}




# ---------------------------
#     GET ALL STUDENTS
# ---------------------------
@app.route("/students/show_all_students", methods=["GET"])
def get_students():
    try:
        # Connect to MySQL
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)  # dictionary=True returns rows as dicts

        # Query all students
        cur.execute("SELECT * FROM student_details;")
        students = cur.fetchall()

        # Close connection
        cur.close()
        conn.close()

        return jsonify(students)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
#     GET ONE STUDENT
# ---------------------------
@app.route("/students/<int:id>", methods=["GET"])
def get_student(id):
    for s in students:
        if s["id"] == id:
            return jsonify(s)
    return jsonify({"error": "Student not found"}), 404


# ---------------------------
#     CREATE STUDENT
# ---------------------------
@app.route("/students", methods=["POST"])
def create_student():
    data = request.json

    new_student = {
        "id": students[-1]["id"] + 1 if students else 1,
        "name": data.get("name"),
        "age": data.get("age"),
        "course": data.get("course")
    }

    students.append(new_student)
    return jsonify(new_student), 201


# ---------------------------
#      UPDATE STUDENT
# ---------------------------
@app.route("/students/<int:id>", methods=["PUT"])
def update_student(id):
    data = request.json

    for s in students:
        if s["id"] == id:
            s["name"] = data.get("name", s["name"])
            s["age"] = data.get("age", s["age"])
            s["course"] = data.get("course", s["course"])
            return jsonify(s)

    return jsonify({"error": "Student not found"}), 404


# ---------------------------
#      DELETE STUDENT
# ---------------------------
@app.route("/students/<int:id>", methods=["DELETE"])
def delete_student(id):
    for s in students:
        if s["id"] == id:
            students.remove(s)
            return jsonify({"message": "Deleted successfully"})

    return jsonify({"error": "Student not found"}), 404

# ---------------------------
#     GET AVAILABLE COURSES
# ---------------------------
@app.route("/courses", methods=["GET"])
def get_courses():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT course FROM student_details;")
        courses = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(courses)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
#      RUN SERVER
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)

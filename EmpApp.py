from flask import Flask, render_template, request
from pymysql import connections
import boto3

app = Flask(__name__)

# Replace with your RDS credentials
db_conn = connections.Connection(
    host='aws-foundation-rds.c1kwquuyetxc.us-east-1.rds.amazonaws.com',
    port=3306,
    user='root',
    password='123456789',
    db='employee'
)

@app.route("/addemp", methods=['GET', 'POST'])
def home():
    return render_template('AddEmp.html')

@app.route("/addemp", methods=['POST'])
def AddEmp():
    emp_id = request.form['emp_id']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    pri_skill = request.form['pri_skill']
    location = request.form['location']
    emp_image_file = request.files['emp_image_file']

    insert_sql = "INSERT INTO employee VALUES (%s, %s, %s, %s, %s)"
    cursor = db_conn.cursor()

    if emp_image_file.filename == "":
        return "Please select a file"

    try:
        cursor.execute(insert_sql, (emp_id, first_name, last_name, pri_skill, location))
        db_conn.commit()

        # Upload image file to S3
        emp_image_file_name_in_s3 = "emp-id-" + str(emp_id) + "_image_file"
        s3 = boto3.resource('s3')

        try:
            print("Data inserted in MySQL RDS... uploading image to S3...")
            s3.Bucket('aws-foundation-bucket-12345').put_object(Key=emp_image_file_name_in_s3, Body=emp_image_file)

            bucket_location = boto3.client('s3').get_bucket_location(Bucket='aws-foundation-bucket')
            s3_location = "" if bucket_location['LocationConstraint'] is None else '-' + bucket_location['LocationConstraint']

            object_url = "https://s3{0}.amazonaws.com/aws-foundation-bucket-12345/{1}".format(
                s3_location,
                emp_image_file_name_in_s3
            )

            # Save image file metadata in DynamoDB
            print("Uploading to S3 success... saving metadata in DynamoDB...")
            dynamodb_client = boto3.client('dynamodb')
            try:
                response = dynamodb_client.put_item(
                    TableName='employee-images-table',
                    Item={
                        'empid': {'N': emp_id},
                        'image_url': {'S': object_url}
                    }
                )
            except Exception as e:
                program_msg = "Flask could not update DynamoDB table with S3 object URL"
                return render_template('addemperror.html', errmsg1=program_msg, errmsg2=str(e))

        except Exception as e:
            program_msg = "Flask could not upload the file in S3"
            return render_template('addemperror.html', errmsg1=program_msg, errmsg2=str(e))

    except Exception as e:
        return str(e)

    finally:
        cursor.close()

    print("All modifications done...")
    return render_template('AddEmpOutput.html', name=first_name + " " + last_name)

@app.route("/getemp", methods=['GET', 'POST'])
def GetEmp():
    return render_template("GetEmp.html")

@app.route("/fetchdata", methods=['POST'])
def FetchData():
    emp_id = request.form['emp_id']
    select_sql = "SELECT emp_id, first_name, last_name, pri_skill, location FROM employee WHERE emp_id=%s"
    cursor = db_conn.cursor()

    try:
        cursor.execute(select_sql, (emp_id,))
        result = cursor.fetchone()

        # Fetch image URL from DynamoDB
        dynamodb_client = boto3.client('dynamodb')
        try:
            response = dynamodb_client.get_item(
                TableName='employee_image_table',
                Key={
                    'empid': {'N': str(emp_id)}
                }
            )
            image_url = response['Item']['image_url']['S']
        except Exception as e:
            program_msg = "Flask could not fetch image URL from DynamoDB"
            return render_template('getemperror.html', errmsg1=program_msg, errmsg2=str(e))

    except Exception as e:
        return str(e)

    finally:
        cursor.close()

    return render_template("GetEmpOutput.html", id=result[0], fname=result[1], lname=result[2], pri_skill=result[3], location=result[4], image_url=image_url)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
 
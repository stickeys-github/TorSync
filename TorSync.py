import pymysql, subprocess, argparse, shutil, os, ctypes, sys, zipfile, pywinauto, urllib, re, datetime, time
from urllib import request
from pywinauto import Application
from sys import platform
from pathlib import Path

#Example Tor Browser target directory:
#   A:\\Tor' 'Browser' 'x64\\Tor' 'Browser

#Args
parser = argparse.ArgumentParser()

parser.add_argument("-g","--gpg", action="store_true", help="Download gpg windows installer to cwd")

parser.add_argument("-r","--remove", action="store_true", help="Remove a backup from the database & backups directory")
parser.add_argument("-t","--date", type=str, help="Supply a backup by date that you want to remove")

parser.add_argument("-a","--add", action="store_true", help="Add a new backup to the database")
parser.add_argument("-d","--directory", type=str, help="Target directory you want to encrypt & backup")
parser.add_argument("-c","--compression", type=int, help="Specify the level of compression you want")
parser.add_argument("-u","--user", type=str, help="Username for MySQL")
parser.add_argument("-p","--password", type=str, help="Password for MySQL")
#parser.add_argument("-s", "--size", type=int, help="Change the maximum size of all backups when combined")

args = parser.parse_args()

dir = args.directory
compression = args.compression
currdate = "-" + str(datetime.datetime.today().strftime('%Y-%m-%d'))

#put gnupg download in cwd
gnupg_dir = (os.getcwd() + ("\gnupg-w32-2.2.11_20181106.exe"))
dbname = "torsync"

def create_db(user, password):
	db = pymysql.connect("localhost", user, password)
	cursor = db.cursor()
	#create pycryption database
	cursor.execute("CREATE DATABASE IF NOT EXISTS " + dbname)
	db.commit()
	cursor.close()

def create_tb(user, password):
	db = pymysql.connect("localhost", user, password)
	cursor = db.cursor()
	#create backups table
	#create table rows. FILENAME (15), date (char 10), FILETYPE (char 10), size (int)
	cursor.execute("""CREATE TABLE IF NOT EXISTS """ + dbname + """.backups (
		FILENAME  VARCHAR(15),
		DATE  VARCHAR(15),
		FILETYPE  VARCHAR(10),
		FILESIZE  INT
	)""")
	db.commit()
	cursor.close()

def insert_tb(user, password, filename, date, filetype, filesize):
	db = pymysql.connect("localhost", user, password)
	cursor = db.cursor()
	use = "USE " + dbname + ";"
	insert = "INSERT INTO backups (FILENAME, DATE, FILETYPE, FILESIZE) VALUES (\"{}\", \"{}\", \"{}\", \"{}\");".format(filename, date, filetype, str(filesize))
	check = "SELECT * FROM backups;"
	cursor.execute(use)
	cursor.execute(insert)
	cursor.execute(check)
	rows = cursor.fetchall()
	for row in rows:
		print(row)
	db.commit()
	cursor.close()

def remove_tb(user, password, date):
	db = pymysql.connect("localhost", user, password)
	cursor = db.cursor()
	use = "USE " + dbname + ";"
	
#Download gpg installer to cwd
if args.gpg and sys.platform == "win32":

	gnupg_url_win = "https://www.gnupg.org/ftp/gcrypt/binary/gnupg-w32-2.2.11_20181106.exe"
	gnupg_win = urllib.request.urlretrieve(gnupg_url_win, gnupg_dir)

	args.gpg = gnupg_win

	#execute gnupg setup with proper privileges
	proc = subprocess.Popen([args.gpg], shell=True)
	proc.communicate()[0]

	if proc.returncode == 1:

		print("gpg on Windows!")

		#os.environ.update({"__COMPAT_LAYER":"RunAsInvoker"})
		
		#gnupg = Application().start(args.gpg)
		#w_handle = pywinauto.findwindows.find_windows(title=u'Installer Language', class_name='#32770')[0]
		#window = gnupg.window(handle=w_handle)
		#window.set_focus()
		#ctrl = window['&Next >']
		#ctrl.click_input()
		time.sleep(3)
		gnupg_setup = pywinauto.application.Application()
		pwa_app = pywinauto.application.Application()
		w_handle = pywinauto.findwindows.find_windows(title=u'GNU Privacy Guard Setup', class_name='#32770')[0]
		window = gnupg_setup.window_(handle=w_handle)
		window.SetFocus()
	
	else:
		sys.exit()

#Add new backup to database using directory + compression arg
elif args.add and args.directory and args.compression and args.compression > -1 and args.compression < 10 and args.user and args.password:
	print("Adding a new backup!")

	create_db(args.user, args.password)
	create_tb(args.user, args.password)

	bkdir = os.getcwd() + "/backups/Tor-Browser" + currdate

	#Handle duplicate files and folders
	if os.path.isdir(bkdir) == True:
		shutil.rmtree(bkdir)

	try:
		dir = shutil.copytree(dir, bkdir)
	except IOError as e:
		print("Cannot copy directory! Exiting...")
		shutil.rmtree(bkdir)
		sys.exit()

	#Zip file
	zip_file = dir + '.zip'

	#GPG file
	gpg_file = zip_file + '.gpg'

	if os.path.isfile(zip_file) == True:
		print("Found duplicate backup zip! Removing...")
		os.remove(zip_file)
	
	if os.path.isfile(gpg_file) == True:
		print("Found duplicate encrypted backup zip! Removing...")
		os.remove(gpg_file)

	print("zip_name: " + zip_file)

	#Zip up entire target directory
	def zip_directory(zip_file, dir):
		print("Zipping the target directory...")
		zip = zipfile.ZipFile(zip_file,'w',zipfile.ZIP_DEFLATED,compresslevel=compression)

		for dirname, subdirs, files in os.walk(dir):
			zip.write(dirname)
			for filename in files:
					zip.write(os.path.join(dirname, filename))
		zip.close()

	print("Tor Browser backup zipped successfully!")

	#Encrypt file using GPG
	def aes_encrypt(zip_file):
		
		#GPG --- C:\Users\Alex>gpg --sign --passphrase --symmetric --cipher-algo AES256 C:\Users\Alex\Desktop\pycryption\Tor-Browser-2018-11-23.zip
		print("Encrypting the zip file...")
		proc = subprocess.Popen(['gpg','--sign','--passphrase','--symmetric','--cipher-algo','AES256',zip_file])
		print("Encryption successful!")
		#if the process fails then terminate it
		proc.communicate()[0]
		proc.returncode
		if proc == 1:
			proc.terminate()
			sys.exit()
	
	zip_directory(zip_file, dir)
	aes_encrypt(zip_file)
	os.remove(zip_file)
	shutil.rmtree(bkdir)

	#Get the size of the gpg file in MB
	size = os.path.getsize(gpg_file)
	filesize=(size>>20)	

	#Extract the gpg file name from the full path
	filename = re.search(r'\bTor\b-\bBrowser\b', gpg_file).group()
	filetype = re.search(r'.\bzip\b.\bgpg\b', gpg_file).group()
	
	print("Added to torsync database:\n   Filename: " + filename + "\n   Date: " + currdate + "\n   Filetype: " + filetype + "\n   Size: " + str(filesize))

	#Get the GPG file
	print(filesize)
	insert_tb(args.user, args.password, filename, currdate, filetype, filesize)

	print("Please provide arguments correctly!\nExample (1):\n   --add --directory A:\\Your\\target\\directory --compression 8 (1-9) --user 'your_mysql_username' --password 'your_mysql_password'\nExample (2):\n   --user 'your_mysql_username' --password 'your_mysql_password' --remove --date 2018-12-26")
	sys.exit()

elif args.remove and args.user and args.password and args.date:

	print("Removing a backup!")
	supplied = args.date
	if bool(re.match(r'\d\d\d\d-\d\d-\d\d', supplied)) == True:
		print("We have a match!")
		#remove_tb(args.user, args.password, args.date)
	else:
		err = print("Please provide arguments correctly!\nExample (1):\n   --add --directory A:\\Your\\target\\directory --compression 8 (1-9) --user 'your_mysql_username' --password 'your_mysql_password'\nExample (2):\n   --user 'your_mysql_username' --password 'your_mysql_password' --remove --date 2018-12-26")
		sys.exit()
else:
	err = print("Please provide arguments correctly!\nExample (1):\n   --add --directory A:\\Your\\target\\directory --compression 8 (1-9) --user 'your_mysql_username' --password 'your_mysql_password'\nExample (2):\n   --user 'your_mysql_username' --password 'your_mysql_password' --remove --date 2018-12-26")
	sys.exit()

'''print("File encrypted!")
time.sleep(5)
print("Decrypting now...")

enc_zip = (zip_name + '.gpg')

decrypt file takes in new gpg file and output file as parameters
def aes_decrypt(enc_zip,zip_name):
	subprocess.run(['gpg','--output',file,'--decrypt',zip_name])
	
aes_decrypt(file)

print("Decrypting complete!")'''


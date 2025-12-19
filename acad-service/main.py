from fastapi import FastAPI, HTTPException, Query #framework
from fastapi.middleware.cors import CORSMiddleware #agar dapat dipanggil service lain
from pydantic import BaseModel, Field #checking data
from typing import Optional, List #pendokumenan
import psycopg2
from psycopg2.extras import RealDictCursor #(penghubung py dan sql)
import os #konfigurasi db dari variabel
from datetime import datetime
from contextlib import contextmanager #koneksi database
#membuat server API, variabel jadi app
app = FastAPI(title="Product Service", version="1.0.0")

# CORS middleware (izinnnn reques untuk gateway)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'products'),
    'user': os.getenv('DB_USER', 'productuser'),
    'password': os.getenv('DB_PASSWORD', 'productpass')
}

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

class Mahasiswa(BaseModel): #memastikan data valid
    nim: str
    nama: str
    jurusan: str
    angkatan: int = Field(ge=0) #gabole -

# Database connection pool
@contextmanager
def get_db_connection(): #koneksi database sementara
    conn = psycopg2.connect(**DB_CONFIG) #konek ke postgresSQL
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.on_event("startup") #check database , memberi log status (siap/tidak)
async def startup_event():
    try:
        with get_db_connection() as conn:
            print("Acad Service: Connected to PostgreSQL") #check database siap
    except Exception as e:
        print(f"Acad Service: PostgreSQL connection error: {e}")

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "Acad Service is running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/acad/mahasiswa")
async def get_mahasiswas():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor() #kirim sql ke db
            
            query = "SELECT * FROM mahasiswa"

            cursor.execute(query)
            rows = cursor.fetchall()
            #tuple sql jadi json, db ke api
            return [{"nim": row[0], "nama": row[1], "jurusan": row[2], "angkatan": row[3]} for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
from fastapi import Query, HTTPException

@app.get("/api/acad/ips")
async def hitung_ips(nim: str = Query(..., description="NIM Mahasiswa")):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Query join (ambil yg dibutuhkan) mahasiswa + krs + mata kuliah
            query = """ 
                SELECT 
                    m.nim,
                    m.nama,
                    m.jurusan,
                    krs.nilai,
                    mk.sks
                FROM mahasiswa m
                JOIN krs ON krs.nim = m.nim
                JOIN mata_kuliah mk ON mk.kode_mk = krs.kode_mk
                WHERE m.nim = %s
            """ #sql skema
            cursor.execute(query, (nim,)) #penhubung python sql
            rows = cursor.fetchall() #validasi

            if not rows: #ketika data kosng
                raise HTTPException(
                    status_code=404,
                    detail=f"Data akademik untuk NIM {nim} tidak ditemukan"
                )

            # Konversi nilai huruf ke bobot
            bobot_nilai = {
                "A": 4.0,
                "A-": 3.75,
                "B+": 3.5,
                "B": 3.0,
                "B-": 2.75,
                "C+": 2.5,
                "C": 2.0,
                "D": 1.0,
                "E": 0.0
            }

            total_sks = 0
            total_bobot = 0.0

            # Ambil identitas mahasiswa (cukup sekali)
            nim_mhs, nama, jurusan = rows[0][0], rows[0][1], rows[0][2]
            #nilai huruf dari krs.nilai, sks dari mata_kuliah.sks (hasil join SQL)
            for _, _, _, nilai_huruf, sks in rows:
                nilai_bersih = nilai_huruf.strip().upper()
                bobot = bobot_nilai.get(nilai_bersih, 0.0)

                total_sks += sks
                total_bobot += bobot * sks

            ips = round(total_bobot / total_sks, 2) if total_sks > 0 else 0.0

            return {
                "nim": nim_mhs,
                "nama": nama,
                "jurusan": jurusan,
                "total_sks": total_sks,
                "ips": ips
            }

    except HTTPException as e:
        raise e #eror logis (data tidak ada)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) #eror teknis

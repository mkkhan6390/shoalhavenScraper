import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    axios
      .get("http://localhost:5000/api/data")
      .then((res) => setRows(res.data))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div className="container">
      <h1>Scraped Data</h1>

      <table className="styled-table">
        <thead>
          <tr>
            <th>DA Number</th>
            <th>Detail URL</th>
            <th>Description</th>
            <th>Submitted Date</th>
            <th>Decision</th>
            <th>Categories</th>
            <th>Property Address</th>
            <th>Applicant</th>
            <th>Progress</th>
            <th>Fees</th>
            <th>Documents</th>
            <th>Contact Council</th>
          </tr>
        </thead>

        <tbody>
          {rows.map((row) => (
            <tr key={row.DA_Number}>
              <td>{row.DA_Number}</td>

              <td>
                <a href={row.Detail_URL} target="_blank" rel="noreferrer">
                  {row.Detail_URL}
                </a>
              </td>

              <td>{row.Description}</td>
              <td>{row.Submitted_Date}</td>
              <td>{row.Decision}</td>
              <td>{row.Categories}</td>
              <td>{row.Property_Address}</td>
              <td>{row.Applicant}</td>
              <td>{row.Progress}</td>
              <td>{row.Fees}</td>

              <td>
                {row.Documents && row.Documents !== "Not available" ? (
                  <a href={row.Documents} target="_blank" rel="noreferrer">
                    View Documents
                  </a>
                ) : (
                  "Not available"
                )}
              </td>

              <td>{row.Contact_Council}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;

export default function NotFound() {
  return (
    <div className="not-found-container" style={{ padding: '2rem', textAlign: 'center' }}>
      <h1>404 - Page Not Found</h1>
      <p>The requested page could not be found.</p>
      <a href="/" style={{ color: '#2AA1CE', textDecoration: 'underline' }}>
        Return to Home
      </a>
    </div>
  )
}

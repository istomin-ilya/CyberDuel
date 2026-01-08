function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-xl shadow-lg text-center">
        <h1 className="text-3xl font-bold text-blue-600 underline mb-4">
          Hello Tailwind!
        </h1>
        <p className="text-gray-600">
          Frontend is running with Vite + React + TypeScript.
        </p>
        <button className="mt-6 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition">
          Click me
        </button>
      </div>
    </div>
  )
}

export default App
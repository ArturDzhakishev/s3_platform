import { Sidebar } from './Sidebar'

export function Layout({ children }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-56 flex-1 p-8 animate-fade-in">
        {children}
      </main>
    </div>
  )
}

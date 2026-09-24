const priorities = [
  { title: 'Review launch criteria', owner: 'You', status: 'In progress' },
  { title: 'Resolve API dependency', owner: 'Platform', status: 'Blocked' },
  { title: 'Prepare stakeholder update', owner: 'You', status: 'Ready' },
];

export const App = () => (
  <main className="shell">
    <header className="topbar">
      <div>
        <p className="eyebrow">Workspace</p>
        <h1>Execution Partner</h1>
      </div>
      <button type="button" className="primary-action">
        Add priority
      </button>
    </header>

    <section className="summary" aria-label="Execution summary">
      <div>
        <span>Active priorities</span>
        <strong>3</strong>
      </div>
      <div>
        <span>At risk</span>
        <strong>1</strong>
      </div>
      <div>
        <span>Due this week</span>
        <strong>2</strong>
      </div>
    </section>

    <section className="worklist" aria-labelledby="priorities-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Today</p>
          <h2 id="priorities-heading">Priorities</h2>
        </div>
        <span>Updated moments ago</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Work item</th>
              <th>Owner</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {priorities.map((priority) => (
              <tr key={priority.title}>
                <td>{priority.title}</td>
                <td>{priority.owner}</td>
                <td>
                  <span
                    className={`status status-${priority.status.toLowerCase().replace(' ', '-')}`}
                  >
                    {priority.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  </main>
);

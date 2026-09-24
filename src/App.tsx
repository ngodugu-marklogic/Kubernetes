import { useState } from 'react';

import { TeamsLanding } from '@/TeamsLanding';
import { Chatbot } from './Chatbot';

export const App = () => {
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);

  return (
    <>
      <TeamsLanding selectedTeam={selectedTeam} onSelectedTeamChange={setSelectedTeam} />
      <Chatbot selectedTeam={selectedTeam} />
    </>
  );
};

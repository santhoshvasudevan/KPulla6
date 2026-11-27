import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it } from 'vitest';
import WealthPrototype from './WealthPrototype';

it('retains scope when cycling layouts and supports selecting an allocation without hovering', () => {
  render(<MemoryRouter initialEntries={['/dashboard?variant=A']}>
    <WealthPrototype scope="Test scope" currency="EUR" summary={{current_value: 100}}
      health={[]} buckets={[{label: 'Equity', value: 65}, {label: 'Debt', value: 35}]} total={100}
      trend={{data: [], lines: [], label: 'Value History', range: '1Y'}} />
  </MemoryRouter>);
  expect(screen.getByRole('heading', {name: 'Wealth overview'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Next design'}));
  const debt = screen.getByRole('button', {name: /Debt/});
  fireEvent.click(debt);
  expect(debt).toHaveAttribute('aria-pressed', 'true');
  expect(document.querySelector('.wp-ring-label')).toHaveTextContent('Debt35.0%€35.00');
  fireEvent.keyDown(document.body, {key: 'ArrowRight'});
  expect(screen.getByRole('heading', {name: 'Return measures'})).toBeInTheDocument();
  fireEvent.keyDown(document.body, {key: 'ArrowRight'});
  expect(screen.getByRole('heading', {name: 'Wealth overview'})).toBeInTheDocument();
  expect(screen.getByText('Test scope')).toBeInTheDocument();
});

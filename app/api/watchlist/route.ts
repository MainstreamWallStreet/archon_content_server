import { NextResponse } from 'next/server';

const BANSHEE_API_URL = process.env.BANSHEE_API_URL_BASE 
  ? `http://${process.env.BANSHEE_API_URL_BASE}`
  : 'http://localhost:8080';

const BANSHEE_API_KEY = process.env.BANSHEE_API_KEY;

console.log('BANSHEE_API_URL_BASE:', process.env.BANSHEE_API_URL_BASE);
console.log('Using API URL:', BANSHEE_API_URL);

export async function GET() {
  try {
    if (!BANSHEE_API_KEY) {
      console.error('BANSHEE_API_KEY is not set');
      throw new Error('API key is not configured');
    }

    console.log('Fetching watchlist from:', `${BANSHEE_API_URL}/watchlist`);
    const response = await fetch(`${BANSHEE_API_URL}/watchlist`, {
      headers: {
        'X-API-Key': BANSHEE_API_KEY,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.error('Watchlist fetch failed:', response.status, response.statusText);
      const errorData = await response.json().catch(() => null);
      console.error('Error details:', errorData);
      throw new Error('Failed to fetch watchlist');
    }

    const data = await response.json();
    console.log('Watchlist data:', data);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching watchlist:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch watchlist' },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    if (!BANSHEE_API_KEY) {
      console.error('BANSHEE_API_KEY is not set');
      throw new Error('API key is not configured');
    }

    const { symbol } = await request.json();
    if (!symbol) {
      return NextResponse.json(
        { error: 'Symbol is required' },
        { status: 400 }
      );
    }

    const response = await fetch(`${BANSHEE_API_URL}/watchlist`, {
      method: 'POST',
      headers: {
        'X-API-Key': BANSHEE_API_KEY,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ticker: symbol,
        user: 'default' // TODO: Replace with actual user ID when auth is implemented
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      console.error('Add ticker failed:', response.status, error);
      return NextResponse.json(
        { error: error.detail || 'Failed to add ticker' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error adding ticker:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to add ticker' },
      { status: 500 }
    );
  }
} 
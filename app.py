import streamlit as st
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import sqlite3  # Python's built-in SQL library


# it creates  the wide layout as the default streamlit is centered
st.set_page_config(layout="wide")



# --- DATABASE SETUP ---

@st.cache_resource
def setup_database():
    """
    Loads data from CSVs into an in-memory SQLite database.
    Returns a database connection object.
    """
    SCRIPT_DIR = Path(__file__).parent

    MATCHES_FILE_PATH = SCRIPT_DIR / "matches.csv"
    DELIVERIES_FILE_PATH = SCRIPT_DIR / "deliveries.csv"

    try:
        matches_df = pd.read_csv(MATCHES_FILE_PATH)
        deliveries_df = pd.read_csv(DELIVERIES_FILE_PATH)

        # Convert 'date' column for proper sorting
        matches_df['date'] = pd.to_datetime(matches_df['date']).dt.strftime('%Y-%m-%d')

    except FileNotFoundError as e:
        st.error(
            f"Error: {e}. Please make sure both 'matches.csv' and 'deliveries.csv' are in the same directory as 'app.py'.")
        st.stop()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()

    # Create an in-memory SQLite database
    conn = sqlite3.connect(":memory:", check_same_thread=False)

    # Load both DataFrames into SQL tables
    matches_df.to_sql("matches", conn, if_exists="replace", index=False)
    deliveries_df.to_sql("deliveries", conn, if_exists="replace", index=False)

    return conn


@st.cache_data
def run_query(query):
    """
    Runs a SQL query on the database and returns the result as a DataFrame.
    """
    return pd.read_sql_query(query, _conn)


# --- INITIALIZE CONNECTION ---
try:
    _conn = setup_database()
except Exception as e:
    st.error(f"Failed to initialize database: {e}")
    st.stop()

# --- HEADER ---
st.title('🏏 Indian Premier League (IPL) Analysis')
st.write("A dashboard to explore IPL match data using SQL queries.")

# --- UI LAYOUT ---
col1, col2 = st.columns(2, gap="large")

with col1:
    # --- Using Tabs for better UI ---
    tab1, tab2 = st.tabs(["📊 Overall League Stats", "🏏 Batsman Analysis"])

    with tab1:
        st.header("Overall League Statistics")

        # 1. Total Matches Metric
        ipl_matches_played = " SELECT COUNT(DISTINCT id) AS total_ipl FROM matches "
        total_matched_df = run_query(ipl_matches_played)
        total_matched = total_matched_df['total_ipl'].iloc[0]
        st.metric("TOTAL MATCHES PLAYED:", total_matched)

        # 2. Matches per Season
        st.subheader("Matches Per Season")
        season_query = """
        SELECT 
            STRFTIME('%Y', date) as season, 
            COUNT(id) as matches_per_season 
        FROM matches 
        GROUP BY season 
        ORDER BY season;
        """
        season_df = run_query(season_query).set_index("season")
        st.bar_chart(season_df)

        # 3. Top 10 Players
        st.subheader("Top 10 'Player of the Match'")
        pom_query = """
        SELECT 
            player_of_match, 
            COUNT(*) as pom_count 
        FROM matches 
        WHERE player_of_match IS NOT NULL 
        GROUP BY player_of_match 
        ORDER BY pom_count DESC 
        LIMIT 10;
        """
        pom_df = run_query(pom_query).set_index("player_of_match")
        st.bar_chart(pom_df)

    with tab2:
        st.header("Batsman Boundary Analysis")

        # We will try 'batter' first, then 'batsman'
        batsman_col_name = "batter"  # Default to 'batter'
        batsmen_query = "SELECT DISTINCT batter FROM deliveries ORDER BY batter;"
        try:
            batsmen_list = run_query(batsmen_query)['batter'].tolist()
        except pd.errors.DatabaseError:
            try:
                batsman_col_name = "batsman"  # Fallback to 'batsman'
                batsmen_query = "SELECT DISTINCT batsman FROM deliveries ORDER BY batsman;"
                batsmen_list = run_query(batsmen_query)['batsman'].tolist()
            except Exception as e:
                st.error("Could not find 'batter' or 'batsman' column in deliveries.csv.")
                st.stop()

        selected_batsman = st.selectbox('Select a Batsman', batsmen_list, key="batsman_select")

        if selected_batsman:
            boundary_query = f"""
            SELECT 
                SUM(CASE WHEN batsman_runs = 4 THEN 1 ELSE 0 END) as Fours,
                SUM(CASE WHEN batsman_runs = 6 THEN 1 ELSE 0 END) as Sixes
            FROM deliveries
            WHERE {batsman_col_name} = '{selected_batsman}'; 
            """
            boundary_df = run_query(boundary_query)

            fours = boundary_df['Fours'].iloc[0]
            sixes = boundary_df['Sixes'].iloc[0]

            st.subheader(f"Boundary Breakdown for {selected_batsman}")

            # Display as metrics
            b_col1, b_col2 = st.columns(2)
            b_col1.metric("Total Fours (4s)", int(fours) if fours else 0)
            b_col2.metric("Total Sixes (6s)", int(sixes) if sixes else 0)

            # Display pie chart
            if (fours and fours > 0) or (sixes and sixes > 0):
                labels = 'Fours', 'Sixes'
                sizes = [fours, sixes]
                colors = ['#007bff', '#dc3545']  # Blue, Red

                fig, ax = plt.subplots()
                ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                       startangle=90, colors=colors)
                ax.axis('equal')
                st.pyplot(fig)
            else:
                st.write(f"{selected_batsman} has not hit any boundaries.")

# --- INTERACTIVE SQL ANALYSIS (Column 2) ---
with col2:
    # --- Using Tabs for better UI ---
    tab3, tab4 = st.tabs(["🚩 Team Performance", "⚾ Bowler Analysis"])

    with tab3:
        st.header('Team Performance Analysis')

        # Get a list of all unique teams for the dropdown
        teams_query = "SELECT DISTINCT team1 FROM matches ORDER BY team1;"
        teams_list = run_query(teams_query)['team1'].tolist()

        selected_team = st.selectbox('Select a Team to Analyze', teams_list, key="team_select")

        if selected_team:
            st.subheader(f"Analysis for {selected_team}")

            # 1. Query for total matches played
            matches_played_query = f"""
            SELECT COUNT(*) AS total_matches
            FROM matches
            WHERE Team1 = '{selected_team}' OR Team2 = '{selected_team}';
            """
            matches_played_df = run_query(matches_played_query)
            total_matches = matches_played_df['total_matches'].iloc[0]

            # 2. Query for matches won
            matches_won_query = f"""
            SELECT COUNT(*) AS wins
            FROM matches
            WHERE Winner = '{selected_team}';
            """
            matches_won_df = run_query(matches_won_query)
            total_wins = matches_won_df['wins'].iloc[0]

            # 3. Query for matches with no result
            no_result_query = f"""
            SELECT COUNT(*) AS no_result
            FROM matches
            WHERE (Team1 = '{selected_team}' OR Team2 = '{selected_team}')
            AND (winner IS NULL OR winner = 'No Result'); 
            """
            no_result_df = run_query(no_result_query)
            total_no_result = no_result_df['no_result'].iloc[0]

            # 4. Calculate Losses
            total_losses = total_matches - total_wins - total_no_result

            # Display Metrics in Columns
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Total Matches", total_matches)
            m_col2.metric("Wins", total_wins)
            m_col3.metric("Losses", total_losses)
            m_col4.metric("No Result", total_no_result)

            # Win/Loss Pie Chart
            st.subheader("Win/Loss Breakdown")
            if total_matches > 0:
                labels = 'Wins', 'Losses', 'No Result'
                sizes = [total_wins, total_losses, total_no_result]
                colors = ['#4CAF50', '#F44336', '#9E9E9E']  # Green, Red, Gray

                non_zero_sizes = []
                non_zero_labels = []
                non_zero_colors = []
                for size, label, color in zip(sizes, labels, colors):
                    if size > 0:
                        non_zero_sizes.append(size)
                        non_zero_labels.append(label)
                        non_zero_colors.append(color)

                if non_zero_sizes:
                    fig, ax = plt.subplots()
                    ax.pie(non_zero_sizes, labels=non_zero_labels, autopct='%1.1f%%',
                           startangle=90, colors=non_zero_colors)
                    ax.axis('equal')
                    st.pyplot(fig)
                else:
                    st.write("No match data to display in pie chart.")
            else:
                st.write("No matches found for this team.")

            # Top 10 Winning Venues
            st.subheader(f"Top 10 Winning Venues for {selected_team}")
            team_venue_query = f"""
            SELECT 
                venue, 
                COUNT(*) as wins_at_venue
            FROM matches
            WHERE winner = '{selected_team}'
            GROUP BY venue
            ORDER BY wins_at_venue DESC
            LIMIT 10;
            """
            team_venue_df = run_query(team_venue_query).set_index("venue")

            if not team_venue_df.empty:
                st.bar_chart(team_venue_df)
            else:
                st.write(f"{selected_team} has not registered any wins.")

    with tab4:
        st.header("Bowler Wicket Analysis")

        # Get a list of all bowlers
        bowler_query = "SELECT DISTINCT bowler FROM deliveries ORDER BY bowler;"
        try:
            bowler_list = run_query(bowler_query)['bowler'].tolist()
        except Exception as e:
            st.error(f"Could not find 'bowler' column in deliveries.csv: {e}")
            st.stop()

        selected_bowler = st.selectbox('Select a Bowler', bowler_list, key="bowler_select")

        if selected_bowler:
            # 1. Query for total wickets and total balls bowled
            bowler_stats_query = f"""
            SELECT
                COUNT(CASE WHEN dismissal_kind IS NOT NULL AND dismissal_kind NOT IN ('run out', 'retired hurt', 'obstructing the field') THEN 1 ELSE NULL END) as total_wickets,
                COUNT(*) as total_balls
            FROM deliveries
            WHERE bowler = '{selected_bowler}';
            """
            bowler_stats_df = run_query(bowler_stats_query)

            total_wickets = bowler_stats_df['total_wickets'].iloc[0]
            total_balls = bowler_stats_df['total_balls'].iloc[0]

            # Calculate overs string (e.g., "10.5 overs")
            overs_bowled_str = f"{total_balls // 6}.{total_balls % 6}"

            # Display metrics
            st.subheader(f"Career Stats for {selected_bowler}")
            bw_col1, bw_col2 = st.columns(2)
            bw_col1.metric("Total Wickets Taken", total_wickets)
            bw_col2.metric("Total Overs Bowled", overs_bowled_str)

            # 2. Query for wicket types (for the pie chart)
            wicket_types_query = f"""
            SELECT
                dismissal_kind,
                COUNT(*) as wicket_count
            FROM deliveries
            WHERE bowler = '{selected_bowler}'
              AND dismissal_kind IS NOT NULL
              AND dismissal_kind NOT IN ('run out', 'retired hurt', 'obstructing the field')
            GROUP BY dismissal_kind
            ORDER BY wicket_count DESC;
            """
            wicket_types_df = run_query(wicket_types_query)

            st.subheader("Wicket Type Breakdown")

            if not wicket_types_df.empty:
                fig, ax = plt.subplots()
                ax.pie(
                    wicket_types_df['wicket_count'],
                    labels=wicket_types_df['dismissal_kind'],
                    autopct='%1.1f%%',
                    startangle=90
                )
                ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
                st.pyplot(fig)
            else:
                st.write(f"{selected_bowler} has not taken any wickets.")


# --- Using st.container(border=True) for better grouping ---

with st.container(border=True):
    st.header("🏆 Season-by-Season Winners")

    # --- Team names for better appeal ---
    season_data = [
        {"Season": 2008, "Winner": "RR", "Runner-up": "CSK", "Player of Series": "Shane Watson",
         "Purple Cap": "Sohail Tanvir", "Emerging Player": "Shreevats Goswami"},
        {"Season": 2009, "Winner": "DEC", "Runner-up": "RCB", "Player of Series": "Adam Gilchrist",
         "Purple Cap": "RP Singh", "Emerging Player": "Rohit Sharma"},
        {"Season": 2010, "Winner": "CSK", "Runner-up": "MI", "Player of Series": "Sachin Tendulkar",
         "Purple Cap": "Pragyan Ojha", "Emerging Player": "Saurabh Tiwary"},
        {"Season": 2011, "Winner": "CSK", "Runner-up": "RCB", "Player of Series": "Chris Gayle",
         "Purple Cap": "Lasith Malinga", "Emerging Player": "Iqbal Abdulla"},
        {"Season": 2012, "Winner": "KKR", "Runner-up": "CSK", "Player of Series": "Sunil Narine",
         "Purple Cap": "Morné Morkel", "Emerging Player": "Mandeep Singh"},
        {"Season": 2013, "Winner": "MI", "Runner-up": "CSK", "Player of Series": "Shane Watson",
         "Purple Cap": "Dwayne Bravo", "Emerging Player": "Sanju Samson"},
        {"Season": 2014, "Winner": "KKR", "Runner-up": "KXIP", "Player of Series": "Glenn Maxwell",
         "Purple Cap": "Mohit Sharma", "Emerging Player": "Axar Patel"},
        {"Season": 2015, "Winner": "MI", "Runner-up": "CSK", "Player of Series": "Andre Russell",
         "Purple Cap": "Dwayne Bravo", "Emerging Player": "Shreyas Iyer"},
        {"Season": 2016, "Winner": "SRH", "Runner-up": "RCB", "Player of Series": "Virat Kohli",
         "Purple Cap": "Bhuvneshwar Kumar", "Emerging Player": "Mustafizur Rahman"},
        {"Season": 2017, "Winner": "MI", "Runner-up": "RPSG", "Player of Series": "Ben Stokes",
         "Purple Cap": "Bhuvneshwar Kumar", "Emerging Player": "Basil Thampi"},
        {"Season": 2018, "Winner": "CSK", "Runner-up": "SRH", "Player of Series": "Sunil Narine",
         "Purple Cap": "Andrew Tye", "Emerging Player": "Rishabh Pant"},
        {"Season": 2019, "Winner": "MI", "Runner-up": "CSK", "Player of Series": "Andre Russell",
         "Purple Cap": "Imran Tahir", "Emerging Player": "Shubman Gill"},
        {"Season": 2020, "Winner": "MI", "Runner-up": "DC", "Player of Series": "Jofra Archer",
         "Purple Cap": "Kagiso Rabada", "Emerging Player": "Devdutt Padikkal"},
        {"Season": 2021, "Winner": "CSK", "Runner-up": "KKR", "Player of Series": "Harshal Patel",
         "Purple Cap": "Harshal Patel", "Emerging Player": "Ruturaj Gaikwad"},
        {"Season": 2022, "Winner": "GT", "Runner-up": "RR", "Player of Series": "Jos Buttler",
         "Purple Cap": "Yuzvendra Chahal", "Emerging Player": "Umran Malik"},
        {"Season": 2023, "Winner": "CSK", "Runner-up": "GT", "Player of Series": "Shubman Gill",
         "Purple Cap": "Mohammed Shami", "Emerging Player": "Yashasvi Jaiswal"},
        {"Season": 2024, "Winner": "KKR", "Runner-up": "SRH", "Player of Series": "Sunil Narine",
         "Purple Cap": "Harshal Patel", "Emerging Player": "Nitish Kumar Reddy"},
    ]

    season_winners_df = pd.DataFrame(season_data)

    # Create a dropdown to select the season
    selected_season = st.selectbox(
        'Select a Season to see the winners',
        season_winners_df['Season'].unique(),
        index=len(season_winners_df['Season'].unique()) - 1  # Default to the most recent season
    )

    if selected_season:
        # Get the data for the selected season
        season_info = season_winners_df[season_winners_df['Season'] == selected_season].iloc[0]

        # Display the data in 5 columns
        s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)

        s_col1.metric("Winner", season_info['Winner'])
        s_col2.metric("Runner-up", season_info['Runner-up'])
        s_col3.metric("Player of Tournament", season_info['Player of Series'])
        s_col4.metric("Purple Cap (Best Bowler)", season_info['Purple Cap'])
        s_col5.metric("Emerging Player", season_info['Emerging Player'])

# --- MODIFIED: Using st.container(border=True) and showing metrics only ---
with st.container(border=True, key="h2h_container"):
    st.header("⚔️ Head-to-Head (H2H) Analysis")


    h2h_col1, h2h_col2 = st.columns(2)
    team_a = h2h_col1.selectbox('Select Team A', teams_list, index=0, key="h2h_team_a")
    team_b = h2h_col2.selectbox('Select Team B', teams_list, index=1, key="h2h_team_b")

    if team_a and team_b and team_a != team_b:
        st.subheader(f"{team_a} vs. {team_b}")

        # 1. Total H2H Matches
        h2h_matches_query = f"""
        SELECT COUNT(*) as total_matches
        FROM matches
        WHERE (team1 = '{team_a}' AND team2 = '{team_b}') 
           OR (team1 = '{team_b}' AND team2 = '{team_a}');
        """
        h2h_matches_df = run_query(h2h_matches_query)
        h2h_total = h2h_matches_df['total_matches'].iloc[0]

        # 2. Team A Wins
        team_a_wins_query = f"""
        SELECT COUNT(*) as wins
        FROM matches
        WHERE winner = '{team_a}'
          AND ((team1 = '{team_a}' AND team2 = '{team_b}') 
               OR (team1 = '{team_b}' AND team2 = '{team_a}'));
        """
        team_a_wins_df = run_query(team_a_wins_query)
        team_a_wins = team_a_wins_df['wins'].iloc[0]

        # 3. Team B Wins
        team_b_wins_query = f"""
        SELECT COUNT(*) as wins
        FROM matches
        WHERE winner = '{team_b}'
          AND ((team1 = '{team_a}' AND team2 = '{team_b}') 
               OR (team1 = '{team_b}' AND team2 = '{team_a}'));
        """
        team_b_wins_df = run_query(team_b_wins_query)
        team_b_wins = team_b_wins_df['wins'].iloc[0]

        # 4. No Result
        h2h_no_result = h2h_total - team_a_wins - team_b_wins

        # Display H2H metrics
        if h2h_total > 0:
            # --- THIS IS THE DATA YOU WANTED ---
            h2h_m_col1, h2h_m_col2, h2h_m_col3, h2h_m_col4 = st.columns(4)
            h2h_m_col1.metric("Total H2H Matches", h2h_total)
            h2h_m_col2.metric(f"{team_a} Wins", team_a_wins)
            h2h_m_col3.metric(f"{team_b} Wins", team_b_wins)
            h2h_m_col4.metric("No Result", h2h_no_result)

            # --- ALL GRAPH CODE REMOVED ---

        else:
            st.write("These two teams have not played against each other.")

    elif team_a == team_b:
        st.warning("Please select two different teams for Head-to-Head analysis.")